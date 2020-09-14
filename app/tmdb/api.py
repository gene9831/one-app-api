# -*- coding: utf-8 -*-
from flask_jsonrpc import JSONRPCBlueprint
from flask_jsonrpc.exceptions import InvalidRequestError

from . import mongodb, TMDB_CONFIG_ID, MyTMDb, update_config
from ..common import AuthorizationSite, Configs

tmdb_bp = JSONRPCBlueprint('tmdb', __name__)
tmdb_admin_bp = JSONRPCBlueprint('tmdb_admin', __name__, jsonrpc_site=AuthorizationSite)


# -------- tmdb blueprint -------- #
@tmdb_bp.method('TMDB.getDataByItemId')
def get_data_by_item_id(item_id: str) -> dict:
    query = {
        'id': item_id,
        'file.mimeType': {'$regex': '^video'}
    }
    doc = mongodb.item.find_one(query)

    if doc is None:
        raise InvalidRequestError(data={'message': 'You cannot get data for a non-video'})

    tmdb_id = doc.get('tmdb_id')

    if tmdb_id is None:
        tmdb_id = MyTMDb().search_movie_id(doc['name'])

    mongodb.item.update_one({'id': item_id}, {'$set': {'tmdb_id': tmdb_id}})

    doc = mongodb.tmdb.find_one({'id': tmdb_id})
    # tmdb文档存在时
    if doc:
        doc.pop('_id', None)
        return doc

    res_json = MyTMDb().movie(tmdb_id)
    mongodb.tmdb.update_one({'id': tmdb_id}, {'$set': res_json}, upsert=True)
    return res_json


# -------- tmdb_admin blueprint -------- #
@tmdb_admin_bp.method('TMDB.getConfig')
def get_config() -> dict:
    doc = mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID}) or {}
    return Configs(doc).sensitive()


@tmdb_admin_bp.method('TMDB.setConfig')
def set_config(config: dict) -> dict:
    return update_config(Configs(config).original())
