# -*- coding: utf-8 -*-
import datetime
import functools
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
        projection: dict = None
) -> Union[dict, None]:
    if projection is None:
        projection = default_projection
    for item in mongodb.item.aggregate([
        {'$match': {'id': item_id}},
        {
            '$lookup': {
                'from': 'tmdb_movies',
                'localField': 'movie_id',
                'foreignField': 'id',
                'as': 'tmdb_movies'
            }
        },
        {'$unwind': '$tmdb_movies'},
        {'$replaceRoot': {'newRoot': '$tmdb_movies'}},
        {'$project': projection}
    ]):
        return item
    return None


iso_639_1_dict = {
    'en': 100,
    'zh': 99,
    'xx': -1,
}


def get_iso_639_1_value(k):
    if k in iso_639_1_dict.keys():
        return iso_639_1_dict[k]
    return 0


def cmp_number_to_int(a, b):
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def cmp(a, b):
    res = cmp_number_to_int(a['vote_average'], b['vote_average'])
    if res == 0:
        return cmp_number_to_int(
            get_iso_639_1_value(a['iso_639_1']),
            get_iso_639_1_value(b['iso_639_1'])
        )
        pass
    return res


@jsonrpc_bp.method('TMDb.updateMovies', require_auth=True)
def update_movies(drive_ids: Union[str, list]) -> int:
    from app.onedrive.api.manage import get_settings
    from app.onedrive.api import onedrive_root_path

    ids = []

    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    res = 0
    three_month_ago = Utils.str_datetime(fmt='%Y-%m-%d',
                                         timedelta=datetime.timedelta(days=-90))
    seven_days_ago = Utils.utc_datetime(timedelta=datetime.timedelta(-7))

    for drive_id in ids:
        movies_path = get_settings(drive_id)['movies_path']

        for item in mongodb.item.find({
            'parentReference.driveId': drive_id,
            'parentReference.path': Utils.path_join(
                onedrive_root_path, movies_path)
        }):
            # 如果是文件且是视频，则用文件名去匹配tmdb信息
            # 如果是文件夹并且子项有视频，则用文件夹的名字去匹配tmdb信息
            if 'file' in item.keys():
                if not item['file']['mimeType'].startswith('video'):
                    continue
            if 'folder' in item.keys():
                if mongodb.item.count_documents({
                    'parentReference.id': item['id'],
                    'file.mimeType': {'$regex': '^video'}
                }) == 0:
                    continue

            instance = MyTMDb()
            movie_id = item.get('movie_id')
            if movie_id is None:
                movie_id = instance.search_movie_id(item['name'])
                if movie_id is None:
                    # 匹配不到tmdb信息
                    continue
                mongodb.item.update_one(
                    {'id': item['id']},
                    {'$set': {'movie_id': movie_id}}
                )

            if mongodb.tmdb_movies.count_documents({
                'id': movie_id,
                '$or': [
                    # release_data 小于当前日期减3个月（也就是说不是最近上映的）
                    {'release_date': {'$lt': three_month_ago}},
                    # 最近上映的，7天更新一次数据
                    {'lastUpdateTime': {'$gt': seven_days_ago}}
                ]
            }) == 0:
                # 查找 tmdb_movie 文档
                resp_json = instance.movie(movie_id)
                posters = resp_json['images']['posters']
                resp_json['images']['posters'] = sorted(
                    posters,
                    key=functools.cmp_to_key(cmp),
                    reverse=True
                )
                mongodb.tmdb_movies.update_one(
                    {'id': resp_json['id']},
                    {
                        '$set': {
                            **resp_json,
                            'lastUpdateTime': Utils.utc_datetime()
                        }
                    },
                    upsert=True)
                res += 1

    logger.info('update {} movies'.format(res))
    return res


@jsonrpc_bp.method('TMDb.removeMovies', require_auth=True)
def remove_movies() -> int:
    r = mongodb.tmdb_movies.delete_many({})
    return r.deleted_count


@jsonrpc_bp.method('TMDb.getMovie')
def get_movie(movie_id: int) -> dict:
    doc = mongodb.tmdb_movies.find_one({'id': movie_id}, default_projection)
    if doc is None:
        raise InvalidRequestError(message='Invalid movie id')
    return doc


get_movies_projection = {
    **default_projection,
    'poster': '$poster.file_path',
}
get_movies_projection.pop('overview', None)
get_movies_projection.pop('runtime', None)
get_movies_projection.pop('images.backdrops', None)
get_movies_projection.pop('images.posters', None)


@jsonrpc_bp.method('TMDb.getMovies')
def get_movies(projection: dict = None, sort: dict = None, skip: int = 0,
               limit: int = 20) -> list:
    if projection is None:
        projection = get_movies_projection
    if sort is None:
        sort = {'release_date': -1}
    res = []
    for doc in mongodb.tmdb_movies.aggregate([
        {'$set': {'poster': {'$arrayElemAt': ['$images.posters', 0]}}},
        {'$project': projection},
        {'$sort': sort},
        {'$skip': skip},
        {'$limit': limit}
    ]):
        res.append(doc)

    return res


item_projection = {
    '_id': 0, 'id': 1, 'name': 1, 'file': 1, 'folder': 1,
    'lastModifiedDateTime': 1, 'size': 1
}


@jsonrpc_bp.method('TMDb.getItemsByMovieId')
def get_items_by_movie_id(movie_id: int) -> list:
    res = []
    for item in mongodb.item.find({'movie_id': movie_id}, item_projection):
        if 'file' in item.keys():
            res.append(item)
        elif 'folder' in item.keys():
            for itm in mongodb.item.find({'parentReference.id': item['id']},
                                         item_projection):
                res.append(itm)

    return res
