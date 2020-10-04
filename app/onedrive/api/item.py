# -*- coding: utf-8 -*-

from flask import redirect, abort
from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp, jsonrpc_admin_bp
from app.apis import yaml_config
from . import onedrive_route_bp
from .. import mongodb, MDrive

onedrive_root_path = '/drive/root:'


@jsonrpc_bp.method('Onedrive.getItemsByPath')
def get_items_by_path(drive_id: str, path: str, page: int = 1,
                      limit: int = 20, query: dict = None) -> list:
    query = query or {}
    skip = (page - 1) * limit
    root_path = onedrive_root_path + yaml_config.get_v('onedrive_root_path')
    if root_path.endswith('/'):
        root_path = root_path[:-1]

    path = '' if path == '/' else path
    query.update({
        'parentReference.driveId': drive_id,
        'parentReference.path': root_path + path
    })
    docs = []
    for item in mongodb.item.find(query).skip(skip).limit(limit):
        item.pop('_id', None)
        docs.append(item)
    return docs


@jsonrpc_admin_bp.method('Onedrive.listDrivePath')
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
    movies_path = yaml_config.get_v('onedrive_movies_path')

    for item_doc in mongodb.item.find({
        'parentReference.path': {
            '$regex': '^{}{}'.format(onedrive_root_path, movies_path)},
        'file.mimeType': {'$regex': '^video'}
    }).skip(skip).limit(limit):
        item_doc.pop('_id')
        docs.append(item_doc)

    return docs


@jsonrpc_bp.method('Onedrive.getTVSeries')
def get_tv_series(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []
    tv_series_path = yaml_config.get_v('onedrive_tv_series_path')

    for item_doc in mongodb.item.find({
        'parentReference.path': {
            '$regex': '^{}{}'.format(onedrive_root_path, tv_series_path)},
        'file.mimeType': {'$regex': '^video'}
    }).skip(skip).limit(limit):
        item_doc.pop('_id')
        docs.append(item_doc)

    return docs


@jsonrpc_bp.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        raise InvalidRequestError(data={'message': 'Cannot find item'})
    doc.pop('_id', None)
    return doc


@jsonrpc_bp.method('Onedrive.getItemContent')
def get_item_content(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(
            data={'message': 'You cannot get content for a folder'})

    drive = MDrive.create(doc['parentReference']['driveId'])
    return drive.content_url(item_id)


@onedrive_route_bp.route('/<item_id>/<name>', methods=['GET'])
def item_content(item_id, name):
    if mongodb.item.find_one({'id': item_id, 'name': name}) is None:
        abort(404)
    content_url = get_item_content(item_id)
    return redirect(content_url)


@jsonrpc_admin_bp.method('Onedrive.getItemSharedLink')
def get_item_shared_link(item_id: str) -> str:
    cache = mongodb.item_cache.find_one({'id': item_id})
    if cache and cache.get('create_link'):
        return cache['create_link']['direct_link']

    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(
            data={'message': 'You cannot get link for a folder'})

    drive = MDrive.create(doc['parentReference']['driveId'])
    base_down_url = mongodb.drive_cache.find_one({'id': drive.id}).get(
        'base_down_url')

    if base_down_url is None:
        tmp_url = drive.content_url(item_id)
        symbol = 'download.aspx?'
        base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
        mongodb.drive_cache.update_one({'id': drive.id},
                                       {'$set': {
                                           'base_down_url': base_down_url
                                       }})

    res_json = drive.create_link(item_id)

    _link = res_json['link']['webUrl']
    direct_link = base_down_url + _link[_link.rfind('/') + 1:]

    res_json['direct_link'] = direct_link
    mongodb.item_cache.update_one({'id': item_id},
                                  {'$set': {
                                      'drive_id': drive.id,
                                      'create_link': res_json
                                  }},
                                  upsert=True)

    return direct_link


@jsonrpc_admin_bp.method('Onedrive.deleteItemSharedLink')
def delete_item_shared_link(item_id: str) -> int:
    cache = mongodb.item_cache.find_one({'id': item_id})
    if cache is None or cache.get('create_link') is None:
        return -1

    doc = get_item(item_id)
    drive = MDrive.create(doc['parentReference']['driveId'])
    drive.delete_permissions(item_id, cache['create_link']['id'])

    mongodb.item_cache.update_one({'id': item_id},
                                  {'$unset': {'create_link': ''}})
    return 0
