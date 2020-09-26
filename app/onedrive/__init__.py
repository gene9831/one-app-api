# -*- coding: utf-8 -*-
import datetime
import logging
import os
import threading

from app import mongo
from .graph import Auth, Drive
from ..common import CURDCounter
from ..config_helper import MConfigs

logger = logging.getLogger(__name__)
mongodb = mongo.db

project_dir, project_module_name = os.path.split(
    os.path.dirname(os.path.realpath(__file__)))

CURRENT_PATH = os.path.join(project_dir, project_module_name)
DEFAULT_CONFIG_PATH = os.path.join(CURRENT_PATH, 'default_config.yml')


class MDrive(Auth, Drive):
    @staticmethod
    def create_from_doc(drive_cache):
        """
        :param drive_cache: 缓存的token文档
        :return:
        """
        assert drive_cache is not None
        drive = MDrive(**drive_cache)
        return drive

    @staticmethod
    def create(drive_id):
        drive_cache = mongodb.drive_cache.find_one({'id': drive_id})
        return MDrive.create_from_doc(drive_cache)

    @staticmethod
    def authed_drives():
        for drive_cache in mongodb.drive_cache.find():
            drive = MDrive.create_from_doc(drive_cache)
            if drive.token is None:
                logger.warning('drive({}) token is null'.format(drive.id[:16]))
            yield drive

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.had_been_cached = True
        super(MDrive, self).__init__(kwargs.get('token'))

    def do_if_token_updated(self):
        super(MDrive, self).do_if_token_updated()

        if self.id is None:
            self.id = self.store_drive()

        mongodb.drive_cache.update_one({'id': self.id},
                                       {'$set': {'token': self.token}},
                                       upsert=True)
        logger.info('drive({}) token updated.'.format(self.id[:16]))

    def store_drive(self):
        res_json = self.drive()
        r = mongodb.drive.update_one({'id': res_json['id']},
                                     {'$set': res_json},
                                     upsert=True)
        if r.matched_count == 0:
            self.had_been_cached = False
        return res_json['id']

    def update_items(self):
        cache = mongodb.drive_cache.find_one({'id': self.id}) or {}
        delta_link = cache.get('delta_link')

        counter = CURDCounter()

        for data in self.delta(delta_link):
            # if 'error' in data.keys():
            #     raise Exception('{}. {}'.format(data['error'].get('code'),
            #                                     data['error'].get('message')))

            if '@odata.deltaLink' in data.keys():
                delta_link = data['@odata.deltaLink']

            items = data['value']
            for item in items:
                if item['@odata.type'] != '#microsoft.graph.driveItem':
                    continue

                if 'deleted' in item.keys() and item['deleted'].get(
                        'state') == 'deleted':
                    # 删
                    counter.deleted += mongodb.item.delete_one(
                        {'id': item['id']}).deleted_count
                else:
                    # 增、改
                    res = mongodb.item.update_one({'id': item['id']},
                                                  {'$set': item}, upsert=True)
                    if res.matched_count > 0:
                        if res.modified_count > 0:
                            counter.updated += 1
                    else:
                        counter.added += 1

        mongodb.drive_cache.update_one({'id': self.id},
                                       {'$set': {'delta_link': delta_link}})

        logger.info(
            'drive({}) update items: {}'.format(self.id[:16], counter.detail()))
        return counter

    def auto_update_items(self):
        """
        每天24点自动更新
        :return:
        """
        threading.Thread(target=self.update_items).start()

        now = datetime.datetime.now()
        mid_night = datetime.datetime(now.year, now.month, now.day, 23, 59, 59)
        timedelta = mid_night - now

        # 加10s防抖
        timer = threading.Timer(timedelta.seconds + 10, self.auto_update_items)
        timer.name = 'UpdateItems({})'.format(self.id[:16])
        timer.daemon = True
        timer.start()


def init():
    # 清空 auth_temp
    mongodb.auth_temp.delete_many({})

    configs_obj = MConfigs.create(DEFAULT_CONFIG_PATH)

    # 初始化配置文件
    MConfigs(id=MConfigs.Drive).insert_c(configs_obj)
    logger.info('onedrive default configs loaded.')

    # drive相关
    for drive in MDrive.authed_drives():
        # 更新items
        drive.auto_update_items()


init()
