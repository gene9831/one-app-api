# -*- coding: utf-8 -*-

from flask import redirect, abort
from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from app.app_config import g_app_config
from . import onedrive_route_bp
from .. import mongodb, Drive
from ..graph import drive_api

onedrive_root_path = '/drive/root:'


@jsonrpc_bp.method('Onedrive.getItemsByPath')
def get_items_by_path(drive_id: str, path: str, page: int = 1,
                      limit: int = 20, query: dict = None) -> list:
    query = query or {}
    skip = (page - 1) * limit
    root_path = onedrive_root_path + g_app_config.get('onedrive', 'root_path')
    if root_path.endswith('/'):
        root_path = root_path[:-1]

    path = '' if path == '/' else path
    query.update({
        'parentReference.driveId': drive_id,
        'parentReference.path': root_path + path
    })
    docs = []
    for item in mongodb.item.find(query, {'_id': 0}).skip(skip).limit(limit):
        docs.append(item)
    return docs


@jsonrpc_bp.method('Onedrive.listDrivePath', require_auth=True)
def list_drive_path(drive_id: str, path: str) -> list:
    path = path.strip().replace('\\', '/')
    if path.endswith('/'):
        path = path[:-1]

    query = {
        'parentReference.driveId': drive_id,
        'parentReference.path': onedrive_root_path + path
    }

    res = []
    for item in mongodb.item.find(query):
        d = {
            'value': item.get('name') or 'null',
            'type': 'file' if 'file' in item.keys() else 'dir'
        }
        res.append(d)

    return sorted(res, key=lambda x: x['value'].lower())


@jsonrpc_bp.method('Onedrive.getMovies')
def get_movies(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []
    movies_path = g_app_config.get('onedrive', 'movies_path')

    for item_doc in mongodb.item.find({
        'parentReference.path': {
            '$regex': '^{}{}'.format(onedrive_root_path, movies_path)},
        'file.mimeType': {'$regex': '^video'}
    }, {'_id': 0}).skip(skip).limit(limit):
        docs.append(item_doc)

    return docs


@jsonrpc_bp.method('Onedrive.getTVSeries')
def get_tv_series(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []
    tv_series_path = g_app_config.get('onedrive', 'tv_series_path')

    for item_doc in mongodb.item.find({
        'parentReference.path': {
            '$regex': '^{}{}'.format(onedrive_root_path, tv_series_path)},
        'file.mimeType': {'$regex': '^video'}
    }, {'_id': 0}).skip(skip).limit(limit):
        docs.append(item_doc)

    return docs


@jsonrpc_bp.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id}, {'_id': 0})
    if doc is None:
        raise InvalidRequestError(message='Cannot find item')

    return doc


@jsonrpc_bp.method('Onedrive.getItemContentUrl')
def get_item_content_url(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(message='You cannot get content for a folder')

    drive = Drive.create_from_id(doc['parentReference']['driveId'])
    return drive_api.content_url(drive.token, item_id)


@onedrive_route_bp.route('/<item_id>/<name>', methods=['GET'])
def item_content(item_id, name):
    if mongodb.item.find_one({'id': item_id, 'name': name}) is None:
        abort(404)
    content_url = get_item_content_url(item_id)
    return redirect(content_url)


@jsonrpc_bp.method('Onedrive.getItemSharedLink', require_auth=True)
def get_item_shared_link(item_id: str) -> str:
    item_doc = get_item(item_id)
    if 'folder' in item_doc.keys():
        raise InvalidRequestError(message='You cannot get link for a folder')

    cache = mongodb.item_cache.find_one({'id': item_id},
                                        {'create_link': 1}) or {}

    drive_id = item_doc['parentReference']['driveId']
    base_down_url = get_base_down_url(drive_id, item_id)

    resp_json = cache.get('create_link')
    if resp_json is None:
        drive = Drive.create_from_id(drive_id)
        resp_json = drive_api.create_link(drive.token, item_id)
        mongodb.item_cache.update_one({'id': item_id},
                                      {'$set': {
                                          'drive_id': drive_id,
                                          'create_link': resp_json
                                      }},
                                      upsert=True)

    web_url = resp_json['link']['webUrl']
    direct_link = base_down_url + web_url[web_url.rfind('/') + 1:]

    return direct_link


@jsonrpc_bp.method('Onedrive.deleteItemSharedLink', require_auth=True)
def delete_item_shared_link(item_id: str) -> int:
    cache = mongodb.item_cache.find_one({'id': item_id},
                                        {'create_link': 1}) or {}
    if cache.get('create_link') is None:
        return -1

    item_doc = get_item(item_id)
    drive = Drive.create_from_id(item_doc['parentReference']['driveId'])
    drive_api.delete_permissions(drive.token,
                                 item_id,
                                 cache['create_link']['id'])

    mongodb.item_cache.update_one({'id': item_id},
                                  {'$unset': {'create_link': ''}})
    return 0


def get_base_down_url(drive_id, item_id):
    """
    :param drive_id: drive_id 必须存在
    :param item_id: 任意一个有效的 item_id
    :return:
    """
    cache = mongodb.drive_cache.find_one({'id': drive_id}, {'base_down_url': 1})
    base_down_url = cache.get('base_down_url')

    if base_down_url:
        return base_down_url

    drive = Drive.create_from_id(drive_id)
    tmp_url = drive_api.content_url(drive.token, item_id)
    symbol = 'download.aspx?'
    base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
    mongodb.drive_cache.update_one({'id': drive.id},
                                   {'$set': {'base_down_url': base_down_url}})
    return base_down_url
