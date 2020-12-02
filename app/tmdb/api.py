# -*- coding: utf-8 -*-
import datetime
import logging
import threading
import time
from typing import Union, Literal, Optional

from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import mongodb, MyTMDb
from .lang import get_langs
from ..common import Utils

logger = logging.getLogger(__name__)

default_projection = {
    '_id': 0,
    'id': 1,
    'genres': 1,
    'belongs_to_collection': 1,
    'images.backdrops': {'$slice': ["$images.backdrops", 3]},
    "images.posters": {'$slice': ["$images.posters", 3]},
    'original_language': 1,
    'original_title': 1,
    'overview': 1,
    'release_date': 1,
    'runtime': 1,
    'status': 1,
    'title': 1,
    'popularity': 1,
    'vote_average': 1,
    'vote_count': 1
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
                    # lastUpdateTime 在7天内；最近上映的，7天更新一次数据
                    {'lastUpdateTime': {'$gt': seven_days_ago}}
                ]
            }) > 0:
                continue

            # 查找 tmdb_movie 文档
            resp_json = instance.movie(movie_id)
            if 'id' not in resp_json.keys():
                raise InvalidRequestError(
                    message=resp_json.get('status_message'))

            # images
            countries = []
            for c in resp_json['production_countries']:
                countries.append(c['iso_3166_1'])

            langs = get_langs(countries)
            langs.append('null')

            images = instance.movie_images(movie_id, ','.join(langs))
            if 'id' not in images.keys():
                raise InvalidRequestError(
                    message=images.get('status_message'))
            images.pop('id', None)

            def poster_country_not_null(poster):
                iso_639_1 = poster.get('iso_639_1')
                return iso_639_1 is not None and iso_639_1 != 'xx'

            images['posters'] = list(
                filter(poster_country_not_null, images['posters']))

            resp_json['images'] = images

            # directors
            credit = instance.movie_credits(movie_id)
            if 'id' not in credit.keys():
                raise InvalidRequestError(
                    message=credit.get('status_message'))

            def job_is_director(person):
                return person['job'] == 'Director'

            directors = list(filter(job_is_director, credit['crew']))

            for director in directors:
                mongodb.tmdb_directors.update_one(
                    {'id': director['id']},
                    {'$set': {
                        'id': director['id'],
                        'name': director['name'],
                        'profile_path': director['profile_path']
                    }},
                    upsert=True
                )

            resp_json['directors'] = list(
                map(lambda x: {'id': x['id'], 'name': x['name']}, directors))

            mongodb.tmdb_movies.update_one(
                {'id': resp_json['id']},
                {
                    '$set': {
                        **resp_json,
                        'lastUpdateTime': Utils.utc_datetime()
                    }
                },
                upsert=True)

            if resp_json.get('belongs_to_collection') is not None:
                # update collection
                collection_id = resp_json['belongs_to_collection']['id']
                collection_resp = instance.collection(collection_id)
                mongodb.tmdb_collections.update_one(
                    {'id': collection_resp['id']},
                    {'$set': collection_resp},
                    upsert=True
                )

            res += 1

    if res > 0:
        threading.Thread(
            target=trans_director_name,
            name='translate_director_name'
        ).start()

    logger.info('update {} movies'.format(res))
    return res


@jsonrpc_bp.method('TMDb.translateDirectorName', require_auth=True)
def trans_director_name() -> int:
    from app.baidu_trans import baidu_trans
    for item in mongodb.tmdb_directors.find({'name_zh': None}):
        name_zh = baidu_trans(item['name'])
        print(item['name'], name_zh)
        mongodb.tmdb_directors.update_one(
            {'id': item['id']},
            {'$set': {'name_zh': name_zh}}
        )
        time.sleep(0.1)

    # 翻译完后遍历所有movies，把翻译填充上去
    cnt = 0
    for item in mongodb.tmdb_movies.find({'directors.name_zh': None}):
        directors = item['directors']
        new_directors = []
        for director in directors:
            if director.get('name_zh') is None:
                director['name_zh'] = mongodb.tmdb_directors.find_one(
                    {'id': director['id']}
                ).get('name_zh')
            new_directors.append(director)

        mongodb.tmdb_movies.update_one(
            {'id': item['id']},
            {'$set': {'directors': directors}}
        )
        cnt += 1

    logger.info('translate director name done')

    return cnt


@jsonrpc_bp.method('TMDb.removeMovies', require_auth=True)
def remove_movies() -> int:
    r = mongodb.tmdb_movies.delete_many({})
    return r.deleted_count


@jsonrpc_bp.method('TMDb.updateCollections', require_auth=True)
def update_collections(entire: bool = False) -> int:
    pipeline = [
        {'$match': {'belongs_to_collection': {'$ne': None}}},
        {'$group': {'_id': '$belongs_to_collection.id'}},
        {'$lookup': {
            'from': 'tmdb_collections',
            'localField': '_id',
            'foreignField': 'id',
            'as': 'collections'
        }}
    ]

    if not entire:
        pipeline.extend([{'$match': {'collections': {'$size': 0}}}])

    res = 0
    instance = MyTMDb()
    for collection in mongodb.tmdb_movies.aggregate(pipeline):
        resp_json = instance.collection(collection['_id'])
        mongodb.tmdb_collections.update_one({'id': resp_json['id']},
                                            {'$set': resp_json},
                                            upsert=True)
        res += 1

    return res


@jsonrpc_bp.method('TMDb.getMovie')
def get_movie(movie_id: int) -> dict:
    doc = mongodb.tmdb_movies.find_one({'id': movie_id}, default_projection)
    if doc is None:
        raise InvalidRequestError(message='Invalid movie id')
    return doc


get_movies_projection = {
    **default_projection,
    'poster_path': '$poster.file_path',
}
get_movies_projection.pop('overview', None)
get_movies_projection.pop('runtime', None)
get_movies_projection.pop('images.backdrops', None)
get_movies_projection.pop('images.posters', None)
get_movies_projection.pop('belongs_to_collection', None)


@jsonrpc_bp.method('TMDb.getMovies')
def get_movies(
        match: dict = None,
        skip: int = 0, limit: int = 25,
        order: Literal['asc', 'desc'] = 'asc',
        order_by: Literal[
            'release_date', 'vote_average', 'popularity'] = 'release_date'
) -> dict:
    if match is None:
        match = {}
    for result in mongodb.tmdb_movies.aggregate([
        {'$match': match},
        {'$set': {'poster': {'$arrayElemAt': ['$images.posters', 0]}}},
        {'$project': get_movies_projection},
        {'$facet': {
            'count': [{'$count': 'count'}],
            'list': [
                {'$sort': {
                    order_by: 1 if order == 'asc' else -1,
                    # 多个电影vote_average相同，导致sort排序不稳定，再加个title字段
                    'title': 1
                }},
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
        return result

    return {'count': 0, 'list': []}


item_projection = {
    '_id': 0, 'id': 1, 'name': 1, 'file': 1, 'folder': 1,
    'lastModifiedDateTime': 1, 'size': 1
}


@jsonrpc_bp.method('TMDb.getCollection')
def get_collection(collection_id: int) -> Optional[dict]:
    for item in mongodb.tmdb_collections.aggregate([
        {'$match': {'id': collection_id}},
        {'$unwind': '$parts'},
        {'$project': {'parts.overview': 0}},
        {'$sort': {'parts.release_date': 1}},
        {'$lookup': {
            'from': 'tmdb_movies',
            'localField': 'parts.id',
            'foreignField': 'id',
            'as': 'movies'
        }},
        {'$addFields': {'parts.exist': {'$cond': [
            {'$eq': [{'$size': '$movies'}, 0]}, False, True]
        }}},
        {'$group': {
            '_id': '$id',
            'id': {'$first': '$id'},
            'name': {'$first': '$name'},
            'parts': {'$push': '$parts'}
        }},
        {'$unset': '_id'}
    ]):
        return item

    return None


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
    if len(res) == 0:
        # 没有资源
        mongodb.tmdb_movies.delete_one({'id': movie_id})

    return res


@jsonrpc_bp.method('TMDb.getMovieGenres')
def get_movie_genres() -> list:
    res = []

    for item in mongodb.tmdb_genres.find({}, {'_id': 0}):
        res.append(item)

    return res
