# -*- coding: utf-8 -*-
import logging
import re

from flask_jsonrpc.exceptions import InvalidRequestError

from app import mongo
from .tmdb import TMDb

logger = logging.getLogger(__name__)
mongodb = mongo.db

TMDB_CONFIG_ID = 'tmdb_config'


class MyTMDb(TMDb):

    @classmethod
    def set_session(cls, **kwargs):
        super().set_session(**kwargs)

        doc = mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID}) or {}

        for k in default_params.keys():
            TMDb.session.params.update({k: doc.get(k)})

        TMDb.session.proxies = doc.get('proxies') or {}

    @classmethod
    def search_movie_id(cls, filename):
        name, year = cls.parse_file_name(filename)

        if name is None:
            raise InvalidRequestError(data={'message': 'Invalid filename'})

        res_json = cls.search(name, year)

        if 'total_results' not in res_json.keys():
            if 'errors' in res_json.keys():
                raise InvalidRequestError(data={'message': res_json['errors']})
            raise InvalidRequestError(data={'message': res_json.get('status_message')})

        if res_json['total_results'] < 1:
            raise InvalidRequestError(data={'message': 'Total results: 0'})

        return res_json['results'][0]['id']

    @classmethod
    def movie(cls, movie_id, params=None):
        params = {
            'append_to_response': 'images',
            'include_image_language': 'en,null',  # 海报和背景图的地区没有国内的，因为国内的广告实在太多了
        }
        res_json = super().movie(movie_id, params=params)
        if 'id' not in res_json.keys():
            raise InvalidRequestError(data={'message': res_json.get('status_message')})
        return res_json

    @staticmethod
    def parse_file_name(s):
        # 倒置字符串是为了处理资源本身名字带年份的情况
        # 比如2012世界某日这部电影"2012.2009.1080p.BluRay"
        s = s[::-1]
        # 用[.]或[ ]分隔的文件名都可以解析，其他则不行
        result = re.search(r'[. ]\d{4}[. ]', s)
        if result is None:
            return None, None

        name = s[result.span()[1]:][::-1].replace('.', ' ').strip()
        year = result.group()[::-1].replace('.', ' ').strip()
        return name, year


default_params = {
    'api_key': None,
    'language': 'zh-cn',
}

default_configs = {
    'proxies': {}
}


def init():
    if mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID}) is None:
        mongodb.tmdb.insert_one({'id': TMDB_CONFIG_ID})

    for k, v in default_params.items():
        if mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID, k: {'$exists': False}}):
            mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID}, {'$set': {k: v}})

    for k, v in default_configs.items():
        if mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID, k: {'$exists': False}}):
            mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID}, {'$set': {k: v}})


init()
