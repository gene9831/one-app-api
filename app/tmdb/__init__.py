# -*- coding: utf-8 -*-
import logging
import re

from flask_jsonrpc.exceptions import InvalidRequestError

from app import mongo
from app.apis import yaml_config
from .tmdb import TMDb

logger = logging.getLogger(__name__)
mongodb = mongo.db


class MyTMDb(TMDb):

    def __init__(self):
        super().__init__()

        self.session.params.update(
            {'language': yaml_config.get_v('tmdb_language'),
             'include_adult': False})

        self.session.headers.update(
            {'Authorization': yaml_config.get_v('tmdb_bearer_token')})

        self.session.proxies.update(
            {'http': 'http://' + yaml_config.get_v('tmdb_proxy'),
             'https': 'https://' + yaml_config.get_v('tmdb_proxy')})

    def movie(self, movie_id, params=None):
        params = {
            'append_to_response': 'images',
            'include_image_language': 'en,null',  # 海报和背景图的地区没有国内的，因为国内的广告实在太多了
        }
        res_json = super().movie(movie_id, params=params)
        if 'id' not in res_json.keys():
            raise InvalidRequestError(
                data={'message': res_json.get('status_message')})
        return res_json

    def search_movie_id(self, filename):
        name, year = self.parse_movie_name(filename)

        if name is None:
            raise InvalidRequestError(data={'message': 'Invalid filename'})

        res_json = self.search(name, year)

        if 'total_results' not in res_json.keys():
            if 'errors' in res_json.keys():
                raise InvalidRequestError(data={'message': res_json['errors']})
            raise InvalidRequestError(
                data={'message': res_json.get('status_message')})

        if res_json['total_results'] < 1:
            raise InvalidRequestError(data={'message': 'Total results: 0'})

        return res_json['results'][0]['id']

    @staticmethod
    def parse_movie_name(s):
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

    @staticmethod
    def parse_tv_series_name(s):
        pass


def init():
    from . import api


init()
