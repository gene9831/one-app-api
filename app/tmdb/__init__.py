# -*- coding: utf-8 -*-
import logging
import re

from flask_jsonrpc.exceptions import InvalidRequestError

from app import mongo
from app.app_config import g_app_config
from .tmdb import TMDb

logger = logging.getLogger(__name__)
mongodb = mongo.db


class MyTMDb(TMDb):

    def __init__(self):
        super().__init__()

        self.session.params.update(
            {'language': g_app_config.get('tmdb', 'language'),
             'include_adult': False})

        self.session.headers.update(
            {'Authorization': g_app_config.get('tmdb', 'bearer_token')})

        proxy = g_app_config.get('tmdb', 'proxy')
        if len(proxy) > 0:
            self.session.proxies.update(
                {'http': 'http://' + proxy, 'https': 'http://' + proxy})

    def search_movie_id(self, filename):
        name, year = self.parse_movie_name(filename)

        if name is None:
            return None

        params_list = [
            {'query': name, 'primary_release_year': year},
            {'query': name, 'year': year}
        ]

        resp_json = None
        for params in params_list:
            resp_json = self.search_movie(params)

            if 'total_results' in resp_json.keys() and \
                    resp_json['total_results'] > 0:
                break

        if 'total_results' not in resp_json.keys():
            if 'errors' in resp_json.keys():
                raise InvalidRequestError(message=resp_json['errors'])
            raise InvalidRequestError(message=resp_json.get('status_message'))

        if resp_json['total_results'] < 1:
            return None

        return resp_json['results'][0]['id']

    def get_movie_genres(self):
        if mongodb.tmdb_genre.count_documents({}) > 0:
            return
        resp_json = self.genre_movie()
        if 'genres' not in resp_json.keys():
            logger.error('Get movie genres failed.')
            return

        mongodb.tmdb_genre.insert_many(resp_json['genres'])

    @staticmethod
    def parse_movie_name(s):
        # 倒置字符串是为了处理资源本身名字带年份的情况
        # 比如2012世界某日这部电影"2012.2009.1080p.BluRay"
        s = re.sub(r'[()]', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        s = s[::-1]
        # 用[.]或[ ]分隔的文件名都可以解析，其他则不行
        # search发布年份
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

    MyTMDb().get_movie_genres()


init()
