# -*- coding: utf-8 -*-
import datetime
import logging
import threading

from app import mongo
from .graph import auth, drive_api
from ..common import CURDCounter

logger = logging.getLogger(__name__)
mongodb = mongo.db


class Drive:
    token_lock = threading.Lock()
    update_lock = threading.Lock()

    @staticmethod
    def create_from_id(drive_id):
        return Drive(id=drive_id)

    @staticmethod
    def create_from_token(token):
        return Drive(token=token)

    @staticmethod
    def all_drive_ids():
        for doc in mongodb.drive.find({}, {'id': 1}):
            yield doc['id']

    def __init__(self, **kwargs):
        """
        建议使用 create_from_id 和 create_from_token 方法来实例化
        初始化时， id 和 token 参数二选一
        选择 token 参数初始化后，需要调用 store_drive 方法，让 id 和 user 有效
        :param kwargs:
        """
        self._id = kwargs.get('id')
        self._token = kwargs.get('token')
        self._user = kwargs.get('user')

        if self._id is None and self._token is None:
            raise Exception('args of "id" or "token" must pass one')

    @property
    def id(self):
        if self._id:
            return self._id
        self.store_drive()
        return self._id

    @property
    def token(self):
        with self.token_lock:
            if self._token:
                token = self._token
            else:
                doc = mongodb.drive.find_one({'id': self.id}, {'token': 1})
                token = (doc or {}).get('token')

            # TODO new_token 为 None 时怎么处理
            new_token = auth.refresh_token(token)

            if new_token != token:
                # updated
                self._token = new_token
                mongodb.drive.update_one({'id': self.id},
                                         {'$set': {'token': new_token}})
                logger.info(
                    'drive({}) token updated'.format(self.user['email']))
            return new_token

    @property
    def user(self):
        if self._user:
            return self._user
        if self._id:
            drive_json = mongodb.drive.find_one({'id': self.id}, {'owner': 1})
            self._user = drive_json['owner']['user']
        else:
            self.store_drive()
        return self._user

    def store_drive(self):
        """
        存储 drive，并让 id 和 user 有效
        :return:
        """
        drive_json = drive_api.drive(self.token)
        self._id = drive_json['id']
        self._user = drive_json['owner']['user']

        res = mongodb.drive.update_one(
            {'id': self.id},
            {'$set': {**drive_json, 'token': self.token}},
            upsert=True
        )
        logger.info('drive({}) stored'.format(self.user['email']))

        return res

    def update(self, exclude_drive=False, full_update=False):
        with self.update_lock:
            # 任务上传成功后或者删除后会调用，这里加锁
            counter = CURDCounter()

            # update drive
            if not exclude_drive:
                drive_json = drive_api.drive(self.token)
                mongodb.drive.update_one({'id': drive_json['id']},
                                         {'$set': drive_json})
                logger.info('drive({}) updated'.format(self.user['email']))

            # update items
            delta_link = None
            if full_update:
                # 先将原有id全部保存，然后每更新一个item，就删除item_temp里对应的id，
                # 最后剩余的id就是已经无效的了
                mongodb.item_temp.delete_many({})
                for item in mongodb.item.find(
                        {'parentReference.driveId': self.id},
                        {'id': 1}
                ):
                    mongodb.item_temp.insert_one({'id': item['id']})
            else:
                drive_doc = mongodb.drive.find_one({'id': self.id},
                                                   {'delta_link': 1})
                delta_link = drive_doc.get('delta_link')

            for resp_json in drive_api.delta(self.token, delta_link):
                if '@odata.deltaLink' in resp_json.keys():
                    delta_link = resp_json['@odata.deltaLink']

                items = resp_json['value']
                for item in items:
                    if item['@odata.type'] != '#microsoft.graph.driveItem':
                        continue

                    if 'deleted' in item.keys() and item['deleted'].get(
                            'state') == 'deleted':
                        # 删
                        counter.deleted += mongodb.item.delete_many({
                            'id': item['id']
                        }).deleted_count
                    else:
                        # 下载HEAD.md或者README.md
                        if (item['name'] == 'README.md' or item[
                            'name'] == 'HEAD.md') and \
                                item['size'] <= 1024 * 1024:
                            from app.onedrive.graph.drive_api import content
                            resp = content(self.token, item['id'])
                            item['content'] = resp.text

                        # 增、改
                        res = mongodb.item.update_one({'id': item['id']},
                                                      {'$set': item},
                                                      upsert=True)
                        if res.matched_count > 0:
                            if res.modified_count > 0:
                                counter.updated += 1
                        else:
                            counter.added += 1

                        if full_update:
                            # 每更新一个item，就删除item_temp里对应的id
                            mongodb.item_temp.delete_many({'id': item['id']})

            mongodb.drive.update_one({'id': self.id},
                                     {'$set': {'delta_link': delta_link}})

            if full_update:
                # 剩余的id就是已经无效的了，删除它
                for item in mongodb.item_temp.find():
                    mongodb.item.delete_many({'id': item['id']})
                    counter.deleted += 1

            logger.info(
                'drive({}) items updated: {}'.format(self.user['email'],
                                                     counter.detail()))
            return counter

    def remove(self):
        email = self.user['email']
        mongodb.drive.delete_many({'id': self.id})
        mongodb.item.delete_many({'parentReference.driveId': self.id})
        logger.info('drive({}) removed'.format(email))


def auto_update():
    """
    每天24点自动更新
    :return:
    """
    drive_ids = []
    for drive_id in Drive.all_drive_ids():
        Drive.create_from_id(drive_id).update()
        drive_ids.append(drive_id)

    from app.tmdb.api.updater import update_movie_data
    update_movie_data(drive_ids)

    now = datetime.datetime.now()
    mid_night = datetime.datetime(now.year, now.month, now.day, 23, 59, 59)
    timedelta = mid_night - now

    # 加10s防抖
    timer = threading.Timer(timedelta.seconds + 10, auto_update)
    timer.name = 'onedrive-auto-updater'
    timer.daemon = True
    timer.start()


def init():
    from . import api
    # 清空 auth_temp
    mongodb.auth_temp.delete_many({})

    # 自动更新items
    auto_update()


init()
