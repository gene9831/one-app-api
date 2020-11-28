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

    def movie(self, movie_id, params=None):
        params = {
            'append_to_response': 'images',
            'include_image_language': 'en,null',  # 海报和背景图的地区没有国内的，因为国内的广告实在太多了
        }
        resp_json = super().movie(movie_id, params=params)
        if 'id' not in resp_json.keys():
            raise InvalidRequestError(message=resp_json.get('status_message'))
        return resp_json

    def collection(self, collection_id, params=None):
        params = {'language': 'en-US', }
        resp_json = super(MyTMDb, self).collection(collection_id, params=params)
        resp_json_zh = super(MyTMDb, self).collection(collection_id)
        # 提取中文部分文字信息，其他的用英文信息
        resp_json['name'] = resp_json_zh['name']
        resp_json['overview'] = resp_json_zh.get('overview') or ''
        # 这个字典是movie_id对应数组下标，保险起见
        # 因为有可能两个parts中的movie_id对应的下标不一样
        movie_id_to_index = {}
        for i in range(len(resp_json['parts'])):
            movie_id_to_index[resp_json['parts'][i]['id']] = i
        for item in resp_json_zh['parts']:
            if item['id'] not in movie_id_to_index.keys():
                continue
            resp_json['parts'][
                movie_id_to_index[item['id']]
            ]['title'] = item['title']
            resp_json['parts'][
                movie_id_to_index[item['id']]
            ]['overview'] = item['overview']

        return resp_json

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
        if mongodb.tmdb_genres.count_documents({}) > 0:
            return
        resp_json = self.genre_movie()
        if 'genres' not in resp_json.keys():
            logger.error('Get movie genres failed.')
            return

        mongodb.tmdb_genres.insert_many(resp_json['genres'])

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
