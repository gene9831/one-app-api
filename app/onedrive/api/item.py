# -*- coding: utf-8 -*-
import datetime
import os
import time
from typing import Union

from flask import redirect, abort
from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import onedrive_route_bp, onedrive_root_path
from .manage import get_settings
from .. import mongodb, Drive
from ..graph import drive_api
from ...common import Utils

TZ_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


@jsonrpc_bp.method('Onedrive.getItemsByPath')
def get_items_by_path(drive_id: str, path: str, page: int = 1,
                      limit: int = 20, query: dict = None,
                      pwd: str = None) -> Union[list, int]:
    """
    文件夹移动或者重命名后，使用 deltaLink 更新，不会更新文件夹的子项的数据。
    也就是说使用本方查找重命名过的文件夹的子项的结果是空的，全量更新后没有问题。
    :param drive_id:
    :param path:
    :param page:
    :param limit:
    :param query:
    :param pwd:
    :return:
    """
    query = query or {}
    skip = (page - 1) * limit

    path_settings = get_settings(drive_id)
    path = Utils.path_join(path_settings['root_path'], path, root=False)

    query.update({
        'parentReference.driveId': drive_id,
        'parentReference.path': onedrive_root_path + path
    })

    is_movies_path = False
    if path == path_settings['movies_path']:
        is_movies_path = True

    docs = []
    for item in mongodb.item.find(query, {
        '_id': 0, 'id': 1, 'name': 1, 'file': 1, 'folder': 1,
        'lastModifiedDateTime': 1, 'size': 1
    }).skip(skip).limit(limit):
        if item['name'].startswith('.pwd'):
            if pwd is None:
                # 需要密码
                return 401
            if pwd != item['name'].replace('.pwd=', ''):
                # 密码错误
                raise InvalidRequestError(message='Wrong password')
        if item['name'].startswith('.'):
            # 不显示以.开头的文件
            continue
        if is_movies_path:
            from app.tmdb.api import get_movie_data_by_item_id
            tmdb_info = get_movie_data_by_item_id(
                item['id'], {'_id': 0, 'id': 1, 'title': 1})
            if tmdb_info is not None:
                item['tmdb_info'] = tmdb_info
                item['tmdb_info']['type'] = 'movie'
        docs.append(item)
    return docs


@jsonrpc_bp.method('Onedrive.listDrivePath', require_auth=True)
def list_drive_path(drive_id: str, path: str) -> Union[list, int]:
    """
    path 是目录，返回列表；path 是文件，返回 0
    :param drive_id:
    :param path:
    :return:
    """
    # 根目录为空字符串，其他目录以 '/' 开头
    path = Utils.path_with_slash(path, root=False)

    query = {
        'parentReference.driveId': drive_id,
        'parentReference.path': onedrive_root_path + path
    }

    res = []
    for item in mongodb.item.find(query):
        d = {
            'value': item.get('name') or 'null',
            'type': 'file' if 'file' in item.keys() else 'folder'
        }
        if d['type'] == 'file':
            d['size'] = item['size']
        else:
            d['childCount'] = item['folder']['childCount']
        res.append(d)

    if len(res) == 0 and path != '':
        # 判断是不是一个文件
        d, f = os.path.split(path)
        item_doc = mongodb.item.find_one({
            'name': f,
            'parentReference.driveId': drive_id,
            'parentReference.path': Utils.path_join(onedrive_root_path, d)
        }, {'file': 1}) or {}
        if item_doc.get('file') is not None:
            return 0

    return sorted(res, key=lambda x: x['value'].upper())


# @jsonrpc_bp.method('Onedrive.getMovies')
# def get_movies(drive_id: str, page: int = 1, limit: int = 20) -> list:
#     skip = (page - 1) * limit
#     docs = []
#     movies_path = get_settings(drive_id)['movies_path']
#
#     # TODO 不直接判断 mimeType
#     for item_doc in mongodb.item.find({
#         'parentReference.path': {
#             '$regex': '^{}{}'.format(onedrive_root_path, movies_path)},
#         'file.mimeType': {'$regex': '^video'}
#     }, {'_id': 0}).skip(skip).limit(limit):
#         docs.append(item_doc)
#
#     return docs
#
#
# @jsonrpc_bp.method('Onedrive.getTVSeries')
# def get_tv_series(drive_id: str, page: int = 1, limit: int = 20) -> list:
#     skip = (page - 1) * limit
#     docs = []
#     tv_series_path = get_settings(drive_id)['tv_series_path']
#
#     # TODO 不直接判断 mimeType
#     for item_doc in mongodb.item.find({
#         'parentReference.path': {
#             '$regex': '^{}{}'.format(onedrive_root_path, tv_series_path)},
#         'file.mimeType': {'$regex': '^video'}
#     }, {'_id': 0}).skip(skip).limit(limit):
#         docs.append(item_doc)
#
#     return docs


@jsonrpc_bp.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id}, {'_id': 0})
    if doc is None:
        raise InvalidRequestError(message='Cannot find item')

    return doc


@jsonrpc_bp.method('Onedrive.getItemContentUrl')
def get_item_content_url(item_id: str, item: dict = None) -> str:
    item_doc = item or get_item(item_id)

    if 'folder' in item_doc.keys():
        raise InvalidRequestError(message='You cannot get content for a folder')

    if item_doc['size'] > 50 * 1024 * 1024:
        raise InvalidRequestError(message='Large files use shared link')

    drive = Drive.create_from_id(item_doc['parentReference']['driveId'])
    return drive_api.content_url(drive.token, item_id)


@onedrive_route_bp.route('/<item_id>/<name>', methods=['GET'])
def item_content(item_id, name):
    item = mongodb.item.find_one({'id': item_id, 'name': name})
    if item is None:
        abort(404)
    try:
        content_url = get_item_content_url(item_id, item)
        return redirect(content_url)
    except InvalidRequestError:
        abort(404)


@jsonrpc_bp.method('Onedrive.getItemSharedLink')
def get_item_shared_link(item_id: str, item: dict = None) -> Union[str, None]:
    item_doc = item or get_item(item_id)
    if 'folder' in item_doc.keys():
        raise InvalidRequestError(message='You cannot get link for a folder')

    cache = mongodb.item_cache.find_one(
        {
            'id': item_id,
            'create_link.expirationDateTime': {
                '$gt': (datetime.datetime.utcnow() + datetime.timedelta(
                    days=1)).strftime(TZ_FORMAT)
            }
        },
        {'create_link': 1}
    ) or {}
    create_link = (cache or {}).get('create_link')

    if create_link is None:
        return None

    drive_id = item_doc['parentReference']['driveId']
    base_down_url = get_base_down_url(drive_id, item_id)
    web_url = create_link['link']['webUrl']
    share = web_url[web_url.rfind('/') + 1:]
    # download.aspx 加上 '/' 再在后面加任意字符串都行，这里加个文件名方便识别
    direct_link = base_down_url.replace(
        '?share=', '/' + item_doc['name'] + '?share=') + share

    return direct_link


@jsonrpc_bp.method('Onedrive.createItemSharedLink')
def create_item_shared_link(item_id: str) -> str:
    """
    返回3天有效期的资源链接，实际4天有效期，留一天防止链接突然失效
    :param item_id:
    :return:
    """
    item_doc = get_item(item_id)
    direct_link = get_item_shared_link(item_id, item_doc)
    if direct_link:
        return direct_link

    drive_id = item_doc['parentReference']['driveId']
    drive = Drive.create_from_id(drive_id)
    next_4_days = (datetime.datetime.utcnow() + datetime.timedelta(
        days=4)).strftime(TZ_FORMAT)
    resp_json = drive_api.create_link(drive.token, item_id, next_4_days)

    mongodb.item_cache.update_one({'id': item_id},
                                  {'$set': {
                                      'drive_id': drive_id,
                                      'create_link': resp_json
                                  }},
                                  upsert=True)

    base_down_url = get_base_down_url(drive_id, item_id)
    web_url = resp_json['link']['webUrl']
    share = web_url[web_url.rfind('/') + 1:]
    # download.aspx 加上 '/' 再在后面加任意字符串都行，这里加个文件名方便识别
    direct_link = base_down_url.replace(
        '?share=', '/' + item_doc['name'] + '?share=') + share

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
