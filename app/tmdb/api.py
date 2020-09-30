# -*- coding: utf-8 -*-
from flask_jsonrpc.exceptions import InvalidRequestError

from app import blueprint_admin
from . import mongodb, MyTMDb
from ..config_helper import MConfigs


@blueprint_admin.method('TMDb.getDataByItemId')
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


@blueprint_admin.method('TMDb.getConfig')
def get_config() -> dict:
    return MConfigs(id=MConfigs.TMDb).sensitive()


@blueprint_admin.method('TMDb.setConfig')
def set_config(config: dict) -> int:
    configs_obj = MConfigs(id=MConfigs.TMDb)
    return configs_obj.update_c(MConfigs(config)).modified_count
