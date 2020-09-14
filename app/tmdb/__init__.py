# -*- coding: utf-8 -*-
import logging
import os
import re

from flask_jsonrpc.exceptions import InvalidRequestError

from app import mongo
from .tmdb import TMDb
from ..common import Configs

logger = logging.getLogger(__name__)
mongodb = mongo.db

TMDB_CONFIG_ID = 'tmdb_config'

project_dir, project_module_name = os.path.split(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(project_dir, project_module_name, 'default_config.yml')


class MyTMDb(TMDb):

    def __init__(self):
        super().__init__()

        doc = mongodb.tmdb.find_one({'id': TMDB_CONFIG_ID}) or {}
        config_obj = Configs(doc)

        self.session.params.update(config_obj.get_field('params') or {})
        self.session.headers.update(config_obj.get_field('headers') or {})
        self.session.proxies = config_obj.get_v('proxies') or {}

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
        name, year = self.parse_movie_name(filename)

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


def update_config(config, add_if_not_exist=False):
    """
    初始化或更新配置项
    :param config:
    :param add_if_not_exist: True: 不存在时新增，一般用于初始化；
                             False: 存在时才更新，一般用于后面更新配置。
                             更新时不会新增那些不在默认配置里面的配置项
    :return:
    """
    res = {}
    for k, v in config.items():
        res1 = {}
        for _k, _v in v.items():
            complete_k = k + '.' + _k

            query = {
                'id': TMDB_CONFIG_ID,
                complete_k: {'$exists': not add_if_not_exist}
            }

            modified_count = mongodb.tmdb.update_one(
                query, {'$set': {complete_k: _v}}).modified_count
            if modified_count == 1:
                # modified_count 等于 1 说明更新了 key 对应的配置
                res1[_k] = modified_count
        if res1:
            res[k] = res1
    return res


def init():
    default_configs = Configs.create(DEFAULT_CONFIG_PATH).default()
    # 存在则不插入，不存在则插入
    r = mongodb.tmdb.update_one({'id': TMDB_CONFIG_ID},
                                {'$setOnInsert': default_configs},
                                upsert=True)
    # matched_count 等于 0 说明执行了 $setOnInsert
    if r.matched_count == 0:
        logger.info('tmdb default config loaded')
        return

    # 初始化默认配置
    update_config(default_configs, add_if_not_exist=True)


init()
