# -*- coding: utf-8 -*-
import logging
import os
import re

import yaml
from flask_jsonrpc.exceptions import InvalidRequestError

from app import mongo
from .tmdb import TMDb

logger = logging.getLogger(__name__)
mongodb = mongo.db

TMDB_CONFIG_ID = 'tmdb_config'


class MyTMDb(TMDb):

    def __init__(self):
        super().__init__()

        doc = mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID}) or {}
        self.session.params.update(doc.get('params') or {})
        self.session.headers.update(doc.get('headers') or {})
        self.session.proxies = doc.get('proxies') or {}

    def movie(self, movie_id, params=None):
        params = {
            'append_to_response': 'images',
            'include_image_language': 'en,null',  # 海报和背景图的地区没有国内的，因为国内的广告实在太多了
        }
        res_json = super().movie(movie_id, params=params)
        if 'id' not in res_json.keys():
            raise InvalidRequestError(data={'message': res_json.get('status_message')})
        return res_json

    def search_movie_id(self, filename):
        name, year = self.parse_file_name(filename)

        if name is None:
            raise InvalidRequestError(data={'message': 'Invalid filename'})

        res_json = self.search(name, year)

        if 'total_results' not in res_json.keys():
            if 'errors' in res_json.keys():
                raise InvalidRequestError(data={'message': res_json['errors']})
            raise InvalidRequestError(data={'message': res_json.get('status_message')})

        if res_json['total_results'] < 1:
            raise InvalidRequestError(data={'message': 'Total results: 0'})

        return res_json['results'][0]['id']

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


PROJECT_DIR, PROJECT_MODULE_NAME = os.path.split(os.path.dirname(os.path.realpath(__file__)))

default_configs = {}
with open(os.path.join(PROJECT_DIR, PROJECT_MODULE_NAME, 'default_config.yml')) as f:
    default_configs.update(yaml.load(f, Loader=yaml.FullLoader))


def init():
    # 存在则不插入，不存在则插入
    r = mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID},
                                {'$setOnInsert': default_configs},
                                upsert=True)
    # matched_count 等于 0 说明执行了 $setOnInsert
    if r.matched_count == 0:
        return

    # 下面循环都是在 存在 (id 为 TMDB_CONFIG_ID) 的文档的情况下
    for k, v in default_configs.items():
        # 不存在 key 才更新 (key, value)
        # 这里不能加 upsert=True，不然会一直插入新文档
        modified_count = mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID, k: {'$exists': False}},
                                                 {'$set': {k: v}}).modified_count
        # modified_count 等于 1 说明刚刚更新了 key 对应的默认配置
        # modified_count 等于 0 说明已经存在 key 对应的配置，继续遍历看是否有需要增加的配置
        if modified_count == 0 and isinstance(v, dict):
            for _k, _v in v.items():
                _k = k + '.' + _k
                # 不存在 key 才更新 (key, value)
                mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID, _k: {'$exists': False}}, {'$set': {_k: _v}})


init()
