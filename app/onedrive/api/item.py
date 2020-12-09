# -*- coding: utf-8 -*-
import datetime
import os
from typing import Union, Literal

from flask import redirect, abort
from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import onedrive_route_bp, onedrive_root_path
from .manage import get_settings
from .. import mongodb, Drive
from ..graph import drive_api
from ...common import Utils

get_items_projection = {
    '_id': 0, 'id': 1, 'name': 1, 'file': 1, 'folder': 1,
    'lastModifiedDateTime': 1, 'size': 1, 'movie_id': 1, 'tv_series_id': 1,
}


@jsonrpc_bp.method('Onedrive.getItemsByPath')
def get_items_by_path(
        drive_id: str, path: str, skip: int = 0, limit: int = 20,
        query: dict = None, order: Literal['asc', 'desc'] = 'asc',
        order_by: Literal['name', 'lastModifiedDateTime'] = 'name',
        append_md_files=False
) -> dict:
    """
    文件夹移动或者重命名后，使用 deltaLink 更新，不会更新文件夹的子项的数据。
    也就是说使用本方查找重命名过的文件夹的子项的结果是空的，全量更新后没有问题。
    """
    query = query or {}

    settings = get_settings(drive_id)
    path = Utils.path_join(settings['root_path'], path, root=False)

    for result in mongodb.item.aggregate([
        {'$match': {
            **query,
            'parentReference.driveId': drive_id,
            'parentReference.path': onedrive_root_path + path,
            'name': {'$nin': ['README.md', 'HEAD.md']}
        }},
        {'$project': get_items_projection},
        {'$facet': {
            'count': [{'$count': 'count'}],
            'list': [
                {'$sort': {order_by: 1 if order == 'asc' else -1}},
                {'$skip': skip},
                {'$limit': limit}
            ]
        }},
        {'$set': {'count': {'$let': {
            'vars': {'firstElem': {'$arrayElemAt': ['$count', 0]}},
            'in': '$$firstElem.count'
        }}}},
        {'$set': {'count': {'$ifNull': ['$count', {'$toInt': 0}]}}}
    ]):
        if append_md_files:
            md_files = {'head': None, 'readme': None}
            for item in mongodb.item.aggregate([
                {'$match': {
                    'name': {'$in': ['README.md', 'HEAD.md']},
                    'parentReference.driveId': drive_id,
                    'parentReference.path': onedrive_root_path + path,
                }},
                {'$project': {'_id': 0, 'name': 1, 'content': 1}},
            ]):
                if item['name'] == 'README.md':
                    md_files['readme'] = item.get('content')
                if item['name'] == 'HEAD.md':
                    md_files['head'] = item.get('content')

            result = {**result, **md_files}

        return result

    return {'count': 0, 'list': []}


@jsonrpc_bp.method('Onedrive.getMdByPath')
def get_md_by_path(drive_id: str, path: str) -> dict:
    settings = get_settings(drive_id)
    path = Utils.path_join(settings['root_path'], path, root=False)

    res = {
        'head': '',
        'readme': ''
    }

    for item in mongodb.item.aggregate([
        {'$match': {
            'parentReference.driveId': drive_id,
            'parentReference.path': onedrive_root_path + path,
            'name': {'$in': ['README.md', 'HEAD.md']}
        }},
        {'$project': {'_id': 0, 'name': 1, 'content': 1}},
    ]):
        if item['name'] == 'README.md':
            res['readme'] = item.get('content') or ''

        if item['name'] == 'HEAD.md':
            res['head'] = item.get('content') or ''

    return res


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
        raise InvalidRequestError(message='Large file uses shared link')

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

    create_link = item_doc.get('create_link')

    if create_link is not None:
        expiration_date_time = create_link.get('expirationDateTime') or ''
        if expiration_date_time < Utils.utc_datetime(
                timedelta=datetime.timedelta(days=1)):
            create_link = None

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
    next_4_days = Utils.utc_datetime(timedelta=datetime.timedelta(days=4))
    resp_json = drive_api.create_link(drive.token, item_id, next_4_days)

    mongodb.item.update_one({'id': item_id},
                            {'$set': {'create_link': resp_json}})

    base_down_url = get_base_down_url(drive_id, item_id)
    web_url = resp_json['link']['webUrl']
    share = web_url[web_url.rfind('/') + 1:]
    # download.aspx 加上 '/' 再在后面加任意字符串都行，这里加个文件名方便识别
    direct_link = base_down_url.replace(
        '?share=', '/' + item_doc['name'] + '?share=') + share

    return direct_link


@jsonrpc_bp.method('Onedrive.deleteItemSharedLink', require_auth=True)
def delete_item_shared_link(item_id: str) -> int:
    item_doc = get_item(item_id)
    if item_doc.get('create_link') is None:
        return -1

    drive = Drive.create_from_id(item_doc['parentReference']['driveId'])
    drive_api.delete_permissions(drive.token,
                                 item_id,
                                 item_doc['create_link']['id'])

    mongodb.item.update_one({'id': item_id},
                            {'$unset': {'create_link': ''}})
    return 0


def get_base_down_url(drive_id, item_id):
    """
    :param drive_id: drive_id 必须存在
    :param item_id: 任意一个有效的 item_id
    :return:
    """
    drive_doc = mongodb.drive.find_one({'id': drive_id}, {'base_down_url': 1})
    base_down_url = drive_doc.get('base_down_url')

    if base_down_url:
        return base_down_url

    drive = Drive.create_from_id(drive_id)
    tmp_url = drive_api.content_url(drive.token, item_id)
    symbol = 'download.aspx?'
    base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
    mongodb.drive.update_one({'id': drive.id},
                             {'$set': {'base_down_url': base_down_url}})
    return base_down_url
