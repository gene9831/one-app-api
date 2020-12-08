# -*- coding: utf-8 -*-
import datetime
import logging
from typing import Union, List

from app import jsonrpc_bp
from app.common import Utils
from .. import mongodb, MyTMDb
from ..lang import get_langs

logger = logging.getLogger(__name__)


@jsonrpc_bp.method('TMDb.updateMovies', require_auth=True)
def update_movies(drive_ids: Union[str, list]) -> int:
    from app.onedrive.api.manage import get_settings
    from app.onedrive.api import onedrive_root_path

    ids = []
    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    three_month_ago = Utils.str_datetime(fmt='%Y-%m-%d',
                                         timedelta=datetime.timedelta(days=-90))
    seven_days_ago = Utils.utc_datetime(timedelta=datetime.timedelta(-7))
    res = 0
    instance = MyTMDb()

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
            elif 'folder' in item.keys():
                if mongodb.item.count_documents({
                    'parentReference.id': item['id'],
                    'file.mimeType': {'$regex': '^video'}
                }) == 0:
                    continue

            # movie_id
            movie_id = item.get('movie_id')
            if movie_id is None:
                movie_id = instance.search_movie_id(item['name'])
                if movie_id is None:
                    # 匹配不到tmdb信息
                    logger.warning(
                        'No search results for "{}"'.format(item['name']))
                    continue
                mongodb.item.update_one(
                    {'id': item['id']},
                    {'$set': {'movie_id': movie_id}}
                )

            # movie
            if mongodb.tmdb_movie.count_documents({
                'id': movie_id,
                '$or': [
                    # release_data 小于当前日期减3个月（也就是说不是最近上映的）
                    {'release_date': {'$lt': three_month_ago}},
                    # lastUpdateTime 在7天内；最近上映的，7天更新一次数据
                    {'lastUpdateTime': {'$gt': seven_days_ago}}
                ]
            }) > 0:
                # 如三个月之内上映的电影且距离上次更新时间超过7天的话，则更新
                continue

            movie = instance.movie(movie_id)
            if 'id' not in movie.keys():
                logger.error(movie.get('status_message'))
                continue

            movie['lastUpdateTime'] = Utils.utc_datetime()
            mongodb.tmdb_movie.update_one({'id': movie['id']},
                                          {'$set': movie},
                                          upsert=True)
            res += 1

    if res > 0:
        logger.info('{} movie(s) updated.'.format(res))
    return res


@jsonrpc_bp.method('TMDb.updateMovieImages', require_auth=True)
def update_movie_images(
        movie_ids: Union[int, List[int]] = None,
        entire: bool = False
) -> int:
    """
    三种情况：1. 更新缺失的。movie_ids为None，且entire为False
            2. 更新指定的。movie_ids不为None
            3. 更新全部。entire为True，且有最高优先级
    """
    instance = MyTMDb()

    def update_one_movie_images(m_id: int, m_production_countries: list) -> int:
        countries = []
        for country in m_production_countries:
            countries.append(country['iso_3166_1'])

        langs = get_langs(countries)
        langs.append('null')
        images = instance.movie_images(m_id, ','.join(langs))

        if 'id' not in images.keys():
            logger.error(images.get('status_message'))
            return 0
        images.pop('id', None)
        images['lastUpdateTime'] = Utils.utc_datetime()

        # 去掉posters中iso_639_1为None或者xx的
        images['posters'] = list(
            filter(lambda x: x.get('iso_639_1') is not None and x.get(
                'iso_639_1') != 'xx',
                   images['posters'])
        )

        mongodb.tmdb_movie.update_one(
            {'id': m_id},
            {'$set': {'images': images}}
        )
        return 1

    res = 0
    match = None

    if entire:
        # 更新全部
        match = {}
    elif movie_ids is None:
        # 更新缺失的
        match = {'images': None}

    if match is not None:
        for item in mongodb.tmdb_movie.find(
                match,
                {'id': 1, 'production_countries': 1}
        ):
            res += update_one_movie_images(
                item['id'],
                item['production_countries']
            )
        if res > 0:
            logger.info('images of {} movie(s) updated.'.format(res))
        return res

    # 更新指定的
    ids = []
    if isinstance(movie_ids, int):
        ids.append(movie_ids)
    elif isinstance(movie_ids, list):
        ids.extend(movie_ids)

    for movie_id in ids:
        item = mongodb.tmdb_movie.find_one(
            {'id': movie_id},
            {'production_countries': 1}
        )
        if item is None:
            # movie_id无效
            continue
        res += update_one_movie_images(movie_id, item['production_countries'])
    if res > 0:
        logger.info('images of {} movie(s) updated.'.format(res))
    return res


@jsonrpc_bp.method('TMDb.updateDirectors', require_auth=True)
def update_directors(
        movie_ids: Union[int, List[int]] = None,
        entire: bool = False
) -> int:
    """
    三种情况：1. 更新缺失的。movie_ids为None，且entire为False
            2. 更新指定的。movie_ids不为None
            3. 更新全部。entire为True，且有最高优先级
    """
    instance = MyTMDb()

    def update_one_director(m_id: int) -> int:
        credit = instance.movie_credits(m_id)
        if 'id' not in credit.keys():
            logger.error(credit.get('status_message'))
            return 0

        director_ids = list(
            map(
                lambda x: x['id'],
                filter(lambda x: x.get('job') == 'Director', credit['crew'])
            )
        )
        mongodb.tmdb_movie.update_one({'id': m_id},
                                      {'$set': {'directors': director_ids}})
        return 1

    res = 0
    match = None

    if entire:
        # 更新全部
        match = {}
    elif movie_ids is None:
        # 更新缺失的
        match = {'directors': None}

    if match is not None:
        for item in mongodb.tmdb_movie.find(
                match,
                {'id': 1}
        ):
            res += update_one_director(item['id'])
        if res > 0:
            logger.info('directors of {} movie(s) updated.'.format(res))
        return res

    # 更新指定的
    ids = []
    if isinstance(movie_ids, int):
        ids.append(movie_ids)
    elif isinstance(movie_ids, list):
        ids.extend(movie_ids)

    for movie_id in ids:
        if mongodb.tmdb_movie.count_documents({'id': movie_id}) == 0:
            # movie_id无效
            continue
        res += update_one_director(movie_id)
    if res > 0:
        logger.info('directors of {} movie(s) updated.'.format(res))
    return res


@jsonrpc_bp.method('TMDb.updateCollections', require_auth=True)
def update_collections(
        collection_ids: Union[int, List[int]] = None,
        entire: bool = False
) -> int:
    """
    三种情况：1. 更新缺失的。collection_ids为None，且entire为False
            2. 更新指定的。collection_ids不为None
            3. 更新全部。entire为True，且有最高优先级
    """
    instance = MyTMDb()

    def update_one_collection(c_id: int) -> int:
        collection = instance.collection(c_id)
        if 'id' not in collection.keys():
            logger.error(collection.get('status_message'))
            return 0
        mongodb.tmdb_collection.update_one({'id': c_id},
                                           {'$set': collection},
                                           upsert=True)
        return 1

    res = 0
    if entire or collection_ids is None:
        pipeline = [
            {'$match': {'belongs_to_collection': {'$ne': None}}},
            {'$group': {'_id': '$belongs_to_collection.id'}},
            {'$lookup': {
                'from': 'tmdb_collection',
                'localField': '_id',
                'foreignField': 'id',
                'as': 'collections'
            }}
        ]
        if not entire:
            # 匹配缺失的
            pipeline.extend([{'$match': {'collections': {'$size': 0}}}])
        # 更新全部或者更新缺失的
        for item in mongodb.tmdb_movie.aggregate(pipeline):
            res += update_one_collection(item['_id'])
        if res > 0:
            logger.info('{} collection(s) updated.'.format(res))
        return res

    # 更新指定的
    ids = []
    if isinstance(collection_ids, int):
        ids.append(collection_ids)
    elif isinstance(collection_ids, list):
        ids.extend(collection_ids)

    for collection_id in collection_ids:
        res += update_one_collection(collection_id)
    if res > 0:
        logger.info('{} collection(s) updated.'.format(res))
    return res


@jsonrpc_bp.method('TMDb.updatePersons', require_auth=True)
def update_persons(
        person_ids: Union[int, List[int]] = None,
        entire: bool = False
) -> int:
    """
    三种情况：1. 更新缺失的。person_ids为None，且entire为False
            2. 更新指定的。person_ids不为None
            3. 更新全部。entire为True，且有最高优先级
    """
    instance = MyTMDb()

    def update_one_person(p_id: int) -> int:
        person = instance.person(p_id)
        if 'id' not in person.keys():
            logger.error(person.get('status_message'))
            return 0
        mongodb.tmdb_person.update_one({'id': p_id},
                                       {'$set': person},
                                       upsert=True)
        return 1

    res = 0

    if entire or person_ids is None:
        pipelines = [
            {'$project': {'directors': 1}},
            {'$unwind': '$directors'},
            {'$group': {'_id': '$directors'}}
        ]
        if not entire:
            # 匹配缺失的
            pipelines.extend([
                {'$lookup': {
                    'from': 'tmdb_person',
                    'localField': '_id',
                    'foreignField': 'id',
                    'as': 'persons'
                }},
                {'$match': {'persons': {'$size': 0}}}
            ])
        # 更新全部或者更新缺失的
        for item in mongodb.tmdb_movie.aggregate(pipelines):
            res += update_one_person(item['_id'])
        if res > 0:
            logger.info('{} person(s) updated.'.format(res))
        return res

    ids = []
    if isinstance(person_ids, int):
        ids.append(person_ids)
    elif isinstance(person_ids, list):
        ids.extend(person_ids)

    # 更新指定的
    for person_id in person_ids:
        res += update_one_person(person_id)
    if res > 0:
        logger.info('{} person(s) updated.'.format(res))
    return res


@jsonrpc_bp.method('TMDb.updateMovieData', require_auth=True)
def update_movie_data(drive_ids: Union[str, List[str]]):
    # update_persons必须在update_directors之后
    update_movies(drive_ids)
    update_movie_images()
    update_directors()
    update_persons()
    update_collections()
