# -*- coding: utf-8 -*-
import json
import logging
import threading

from app import mongo
from .common import Drive
from ..common import CURDCounter, Utils

logger = logging.getLogger(__name__)
mongodb = mongo.db


class MyDrive(Drive):
    def __init__(self, app_id, app_secret, redirect_url, token=None,
                 drive_id=None, root_path='/drive/root:'):
        super().__init__(app_id, app_secret, redirect_url, token=token)
        self.drive_id = drive_id
        self.root_path = root_path

    def json(self):
        from numbers import Real
        _dict = self.__dict__
        # dictionary cannot change size during iteration. use copy()
        for k, v in _dict.copy().items():
            if not (v is None or
                    isinstance(v, (Real, str, bool, list, dict))):
                _dict.pop(k, None)
        return _dict

    def write_token(self, token):
        super().write_token(token)

        # upsert为True时，如果查询不到，则insert
        mongodb.drive.update_one({'app_id': self.app_id},
                                 {'$set': self.json()},
                                 upsert=True)
        logger.info('app_id({}) token updated'.format(self.app_id))

        if token is None:
            logger.warning('app_id({}) token is null'.format(self.app_id))

    def update_items(self):
        """
        如果app_id对应的drive_id不为None，获取delta link和全部items
        如果app_id对应的drive_id不为None，则访问delta link进行增量更新
        :return:
        """

        doc = mongodb.drive.find_one({'app_id': self.app_id})
        drive_id = doc.get('drive_id')
        delta_link = doc.get('delta_link')

        counter = CURDCounter()

        for data in self.delta(delta_link):
            if delta_link:
                print(json.dumps(data))
            if '@odata.deltaLink' in data.keys():
                delta_link = data['@odata.deltaLink']

            items = data['value']
            for item in items:
                if item['@odata.type'] != '#microsoft.graph.driveItem':
                    continue

                if drive_id is None:
                    drive_id = item['parentReference']['driveId']

                if 'deleted' in item.keys() and item['deleted'].get('state') == 'deleted':
                    # 删
                    counter.deleted += mongodb.item.delete_one({'id': item['id']}).deleted_count
                else:
                    # 增、改
                    res = mongodb.item.update_one({'id': item['id']}, {'$set': item}, upsert=True)
                    if res.matched_count > 0:
                        counter.updated += 1
                    else:
                        counter.added += 1

        mongodb.drive.update_one({'app_id': self.app_id},
                                 {'$set': {
                                     'drive_id': drive_id,
                                     'delta_link': delta_link,
                                 }})

        logger.info('app_id({}) update items: {}'.format(self.app_id, counter.detail()))
        return counter

    @staticmethod
    def drives(verify=True):
        """
        从 mongodb 获取所有已缓存的 drive
        :param verify: 验证 token 是否仍然有效
        :return:
        """
        for doc in mongodb.drive.find():
            drive = MyDrive.create_from_doc(doc)
            if verify:
                if drive.get_token():
                    yield drive
            else:
                yield drive

    @staticmethod
    def create(app_id):
        doc = mongodb.drive.find_one({'app_id': app_id})
        drive = MyDrive.create_from_doc(doc)
        return drive

    @staticmethod
    def create_from_drive_id(drive_id):
        doc = mongodb.drive.find_one({'drive_id': drive_id})
        drive = MyDrive.create_from_doc(doc)
        return drive

    @staticmethod
    def create_from_item_id(item_id):
        doc = mongodb.item.find_one({'id': item_id})
        drive_id = doc['parentReference']['driveId']
        return MyDrive.create_from_drive_id(drive_id)

    @staticmethod
    def create_from_doc(doc):
        return MyDrive(doc['app_id'], doc['app_secret'], doc['redirect_url'], token=doc.get('token'),
                       drive_id=doc.get('drive_id'), root_path=doc.get('root_path'))


class RefreshTimer:
    refresh_interval = 12  # days
    timers = {}
    timers_data = {}

    @staticmethod
    def start_refresh_timer(app_id):
        timer = threading.Timer(Utils.get_seconds(RefreshTimer.refresh_interval),
                                RefreshTimer.refresh_token, (app_id,))
        timer.start()
        RefreshTimer.timers[app_id] = timer
        RefreshTimer.timers_data[app_id] = {
            'lastRefreshTime': Utils.datetime_now(),
            'nextRefreshTime': Utils.datetime_delta(days=RefreshTimer.refresh_interval)
        }

    @staticmethod
    def refresh_token(app_id):
        if MyDrive.create(app_id).get_token() is None:
            RefreshTimer.stop(app_id)
        else:
            RefreshTimer.start_refresh_timer(app_id)

    @staticmethod
    def start(app_id):
        timer = RefreshTimer.timers.get(app_id)
        if isinstance(timer, threading.Timer) and timer.is_alive():
            return

        RefreshTimer.start_refresh_timer(app_id)
        logger.info('app_id({}) start auto refresh token'.format(app_id))

    @staticmethod
    def stop(app_id):
        timer = RefreshTimer.timers.get(app_id)

        if isinstance(timer, threading.Timer):
            timer.cancel()
            logger.info('app_id({}) stop auto refresh token'.format(app_id))

        RefreshTimer.timers.pop(app_id, None)
        RefreshTimer.timers_data.pop(app_id, None)

    @staticmethod
    def show():
        return RefreshTimer.timers_data


def init():
    # 清空 auth_temp
    mongodb.auth_temp.delete_many({})

    # drive相关
    for drive in MyDrive.drives():
        logger.info('app_id({}) is authed from cache'.format(drive.app_id))
        RefreshTimer.start(drive.app_id)

        drive.update_items()


init()
