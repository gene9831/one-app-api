# -*- coding: utf-8 -*-
import logging
from typing import Union

from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import mongodb, MyTMDb
from ..common import Utils

logger = logging.getLogger(__name__)

default_projection = {
    '_id': 0,
    'id': 1,
    'genres': 1,
    'images.backdrops': {'$slice': ["$images.backdrops", 3]},
    "images.posters": {'$slice': ["$images.posters", 3]},
    'original_language': 1,
    'original_title': 1,
    'overview': 1,
    'release_date': 1,
    'runtime': 1,
    'status': 1,
    'title': 1
}


@jsonrpc_bp.method('TMDb.getMovieDataByItemId')
def get_movie_data_by_item_id(
        item_id: str,
        projection=None
) -> Union[dict, None]:
    if projection is None:
        projection = default_projection
    doc = None
    for item in mongodb.item_cache.aggregate([
        {'$match': {'id': item_id}},
        {
            '$lookup': {
                'from': 'tmdb',
                'localField': 'tmdb_id',
                'foreignField': 'id',
                'as': 'tmdb'
            }
        },
        {'$unwind': '$tmdb'},
        {'$replaceRoot': {'newRoot': '$tmdb'}},
        {'$project': projection}
    ]):
        return item
    return doc


@jsonrpc_bp.method('TMDb.getDataByTMDbId')
def get_data_by_tmdb_id(tmdb_id: int) -> dict:
    doc = mongodb.tmdb.find_one({'id': tmdb_id}, default_projection)
    if doc is None:
        raise InvalidRequestError(message='Invalid TMDb id')
    return doc


def update_movie_data_by_item(item: dict) -> int:
    """
    更新指定item的tmdb电影信息
    :param item:
    :return: 0: 未更新；1：已更新；-1：无匹配
    """
    drive_id = item['parentReference']['driveId']
    # 如果是文件且是视频，则用文件名去匹配tmdb信息
    # 如果是文件夹并且子项有视频，则用文件夹的名字去匹配tmdb信息
    if 'file' in item.keys():
        if not item['file']['mimeType'].startswith('video'):
            return -1
    if 'folder' in item.keys():
        if mongodb.item.count_documents({
            'parentReference.driveId': drive_id,
            'parentReference.id': item['id'],
            'file.mimeType': {'$regex': '^video'}
        }) == 0:
            return -1

    cache = mongodb.item_cache.find_one({'id': item['id']}) or {}
    tmdb_id = cache.get('tmdb_id')

    instance = MyTMDb()

    if tmdb_id is None:
        tmdb_id = instance.search_movie_id(item['name'])
        if tmdb_id is None:
            # 匹配不到tmdb信息
            return -1
        mongodb.item_cache.update_one(
            {'id': item['id']},
            {'$set': {'tmdb_id': tmdb_id, 'drive_id': drive_id}},
            upsert=True)

    if mongodb.tmdb.count_documents({'id': tmdb_id}) == 0:
        # 查找 tmdb 文档
        resp_json = instance.movie(tmdb_id)
        mongodb.tmdb.insert_one(resp_json)
        return 1
    return 0


@jsonrpc_bp.method('TMDb.updateMovies', require_auth=True)
def update_movies(drive_ids: Union[str, list]) -> int:
    # TODO 加一个更新时间，超过多久再次更新
    from app.onedrive.api.manage import get_settings
    from app.onedrive.api import onedrive_root_path

    ids = []

    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    res = 0
    for drive_id in ids:
        movies_path = get_settings(drive_id)['movies_path']

        for item in mongodb.item.find({
            'parentReference.driveId': drive_id,
            'parentReference.path': Utils.path_join(onedrive_root_path,
                                                    movies_path)
        }):
            if update_movie_data_by_item(item) > 0:
                res += 1
    logger.info('update {} movies'.format(res))
    return res
