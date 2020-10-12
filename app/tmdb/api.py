# -*- coding: utf-8 -*-

from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from . import mongodb, MyTMDb


# TODO 这个没必要写个api，后台更新即可，顶多加个手动更新api
@jsonrpc_bp.method('TMDb.getDataByItemId', require_auth=True)
def get_data_by_item_id(item_id: str) -> dict:
    cache = mongodb.item_cache.find_one({'id': item_id}) or {}
    tmdb_id = cache.get('tmdb_id')

    if tmdb_id is None:
        # 没有对应的tmdb id
        doc = mongodb.item.find_one({'id': item_id,
                                     'file.mimeType': {'$regex': '^video'}})
        if doc is None:
            raise InvalidRequestError(
                data={'message': 'You cannot get data for a non-video'})
        tmdb_id = MyTMDb().search_movie_id(doc['name'])
        mongodb.item_cache.update_one({'id': item_id},
                                      {'$set': {'tmdb_id': tmdb_id}},
                                      upsert=True)

    doc = mongodb.tmdb.find_one({'id': tmdb_id})
    if doc:
        # tmdb文档存在时
        doc.pop('_id', None)
        return doc

    res_json = MyTMDb().movie(tmdb_id)
    mongodb.tmdb.update_one({'id': tmdb_id}, {'$set': res_json}, upsert=True)
    return res_json
