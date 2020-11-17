# -*- coding: utf-8 -*-

from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import mongodb, MyTMDb

project = {
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


@jsonrpc_bp.method('TMDb.getDataByItemId')
def get_data_by_item_id(item_id: str) -> dict:
    cache = mongodb.item_cache.find_one({'id': item_id}) or {}
    tmdb_id = cache.get('tmdb_id')
    # TODO 还有 type

    instance = MyTMDb()

    if tmdb_id is None:
        # 查找 tmdb_id
        doc = mongodb.item.find_one(
            {
                'id': item_id,
                'file.mimeType': {'$regex': '^video'}
            },
            {'name': 1}
        )
        if doc is None:
            raise InvalidRequestError(message='Wrong item id')

        tmdb_id = instance.search_movie_id(doc['name'])
        mongodb.item_cache.update_one({'id': item_id},
                                      {'$set': {'tmdb_id': tmdb_id}},
                                      upsert=True)

    doc = None
    for d in mongodb.tmdb.aggregate(pipeline=[
        {'$match': {'id': tmdb_id}},
        {'$project': project}
    ]):
        doc = d
        break

    if doc is None:
        # 查找 tmdb 文档
        resp_json = instance.movie(tmdb_id)
        mongodb.tmdb.update_one({'id': tmdb_id},
                                {'$set': resp_json},
                                upsert=True)

        for d in mongodb.tmdb.aggregate(pipeline=[
            {'$match': {'id': tmdb_id}},
            {'$project': project}
        ]):
            doc = d
            break

    return doc
