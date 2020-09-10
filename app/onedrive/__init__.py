# -*- coding: utf-8 -*-
import json
import logging
import threading
from typing import Dict

from app import mongo
from .common import Auth, Drive
from ..common import CURDCounter

logger = logging.getLogger(__name__)
mongodb = mongo.db


class MyAuth(Auth):
    def write_token(self, token):
        super().write_token(token)

        # upsert为True时，如果查询不到，则insert
        mongodb.drive.update_one({'app_id': self.app_id},
                                 {'$set': self.json()},
                                 upsert=True)
        logger.info('app_id({}) token updated'.format(self.app_id))

        if token is None:
            logger.warning('app_id({}) token is null'.format(self.app_id))

    @staticmethod
    def create(app_id):
        doc = mongodb.drive.find_one({'app_id': app_id})
        auth = MyAuth(doc['app_id'], doc['app_secret'],
                      doc['redirect_url'], doc['token'])
        return auth

    @staticmethod
    def authed(verify=True):
        for doc in mongodb.drive.find():
            auth = MyAuth(doc['app_id'], doc['app_secret'], doc['redirect_url'],
                          token=doc.get('token'), drive_id=doc.get('drive_id'), root_path=doc.get('root_path'))
            if verify:
                if auth.get_token():
                    yield auth
            else:
                yield auth


class MyDrive(Drive):
    @staticmethod
    def incr_update(auth):
        # 增量更新
        app_id = auth.app_id
        doc = mongodb.drive.find_one({'app_id': app_id})
        delta_link = doc.get('delta_link')

        if delta_link is None:
            return MyDrive.full_update(auth)

        counter = CURDCounter()

        for data in Drive.delta(auth, delta_link):
            print(json.dumps(data))
            if '@odata.deltaLink' in data:
                delta_link = data['@odata.deltaLink']

            items = data['value']
            for item in items:
                if item['@odata.type'] != '#microsoft.graph.driveItem':
                    continue

                if 'deleted' in item.keys() and item['deleted'].get('state') == 'deleted':
                    # 删
                    res = mongodb.item.delete_one({'id': item['id']})
                    counter.deleted += res.deleted_count
                else:
                    # 增、改
                    res = mongodb.item.update_one({'id': item['id']}, {'$set': item}, upsert=True)
                    if res.modified_count == 1:
                        counter.updated += 1
                    else:
                        counter.added += 1

        mongodb.drive.update_one({'app_id': app_id}, {'$set': {'delta_link': delta_link}})
        logger.info('app_id({}) incremental update: {}'.format(auth.app_id, counter.detail()))
        return counter

    @staticmethod
    def full_update(auth):
        # 全量更新
        app_id = auth.app_id
        drive_id = None
        delta_link = None

        cnt_added = 0
        for data in Drive.delta(auth):
            if '@odata.deltaLink' in data:
                delta_link = data['@odata.deltaLink']

            items = data['value']
            for item in items:
                if item['@odata.type'] != '#microsoft.graph.driveItem':
                    continue

                if drive_id is None:
                    drive_id = item['parentReference']['driveId']
                # 有，就覆盖原来的；没有，就插入
                mongodb.item.update_one({'id': item['id']}, {'$set': item}, upsert=True)
                cnt_added += 1

        mongodb.drive.update_one({'app_id': app_id},
                                 {'$set': {
                                     'drive_id': drive_id,
                                     'delta_link': delta_link,
                                 }})

        counter = CURDCounter(added=cnt_added)
        logger.info('app_id({}) full updated: {}'.format(auth.app_id, counter.detail()))
        return counter

    @staticmethod
    def find_app_id(item_id):
        doc = mongodb.item.find_one({'id': item_id})
        drive_id = doc['parentReference']['driveId']
        doc = mongodb.drive.find_one({'drive_id': drive_id})
        return doc['app_id']


days_12 = 12 * 24 * 3600


class AutoRefreshController:
    timers: Dict[str, threading.Timer] = {}

    @staticmethod
    def auto_refresh_token(app_id):
        auth = MyAuth.create(app_id)
        if auth.get_token() is None:
            AutoRefreshController.stop(app_id)

    @staticmethod
    def start(app_id):
        timer = AutoRefreshController.timers.get(app_id)
        if isinstance(timer, threading.Timer) and timer.is_alive():
            return

        timer = threading.Timer(days_12, AutoRefreshController.auto_refresh_token, (app_id,))
        logger.info('app_id({}) start auto refresh token'.format(app_id))

        AutoRefreshController.timers.update({app_id: timer})

    @staticmethod
    def stop(app_id):
        timer = AutoRefreshController.timers.get(app_id)

        if isinstance(timer, threading.Timer):
            logger.info('app_id({}) stop auto refresh token'.format(app_id))
            timer.cancel()

    @staticmethod
    def show():
        for k, v in AutoRefreshController.timers.items():
            pass


def init():
    # 清空 auth_temp
    mongodb.auth_temp.delete_many({})
    authed = []

    # drive相关
    for auth in MyAuth.authed():
        authed.append(auth)
        logger.info('app_id({}) is authed from cache'.format(auth.app_id))

        AutoRefreshController.start(auth.app_id)

    # item相关
    for auth in authed:
        doc = mongodb.drive.find_one({'app_id': auth.app_id})
        # 如果app_id对应的drive_id为空
        if doc.get('drive_id') is None:
            # 如果app_id对应的drive_id不为None，获取delta link和全部items
            MyDrive.full_update(auth)
        else:
            # 如果app_id对应的drive_id不为None，则访问delta link进行增量更新
            MyDrive.incr_update(auth)


init()
