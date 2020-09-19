# -*- coding: utf-8 -*-
import logging
import os
import threading

from app import mongo
from .onedrive import OneDrive
from ..common import CURDCounter, Utils, Configs

logger = logging.getLogger(__name__)
mongodb = mongo.db

project_dir, project_module_name = os.path.split(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(project_dir, project_module_name, 'default_config.yml')


class MyDrive(OneDrive):
    def __init__(self, **kwargs):
        self.config_obj: Configs = kwargs.get('config_obj')

        super().__init__(kwargs.get('app_id'),
                         kwargs.get('app_secret') or self.config_obj.get_v('app_secret'),
                         kwargs.get('redirect_url') or self.config_obj.get_v('redirect_url'),
                         kwargs.get('token'))

    def do_when_token_updated(self):
        super().do_when_token_updated()
        modified_count = mongodb.drive.update_one(
            {'app_id': self.app_id}, {'$set': {'token': self.token}}).modified_count
        if modified_count > 0:
            logger.info('app_id({}) token updated'.format(self.app_id))

    def update_items(self):
        doc = mongodb.drive.find_one({'app_id': self.app_id})
        delta_link = doc.get('delta_link')

        counter = CURDCounter()

        for data in self.delta(delta_link):
            # if delta_link:
            #     print(json.dumps(data))
            if 'error' in data.keys():
                raise Exception('{}. {}'.format(data['error'].get('code'), data['error'].get('message')))

            if '@odata.deltaLink' in data.keys():
                delta_link = data['@odata.deltaLink']

            items = data['value']
            for item in items:
                if item['@odata.type'] != '#microsoft.graph.driveItem':
                    continue

                if 'deleted' in item.keys() and item['deleted'].get('state') == 'deleted':
                    # 删
                    counter.deleted += mongodb.item.delete_one({'id': item['id']}).deleted_count
                else:
                    # 增、改
                    item['app_id'] = self.app_id
                    res = mongodb.item.update_one({'id': item['id']}, {'$set': item}, upsert=True)
                    if res.matched_count > 0:
                        if res.modified_count > 0:
                            counter.updated += 1
                    else:
                        counter.added += 1

        mongodb.drive.update_one({'app_id': self.app_id},
                                 {'$set': {'delta_link': delta_link, }})

        logger.info('app_id({}) update items: {}'.format(self.app_id, counter.detail()))
        return counter

    @staticmethod
    def drives(update_token=True):
        """
        从 mongodb 获取所有已缓存的 drive
        :param update_token: 是否更新 token。如果不需要请求任何 API，token 没必要更新
        :return:
        """
        for doc in mongodb.drive.find():
            drive = MyDrive.create(doc, update_token=update_token)
            if drive.token is None:
                logger.warning('app_id({}) token is null'.format(drive.app_id))
            yield drive

    @staticmethod
    def create(doc, update_token=True):
        """
        从 create 方法创建的实例都已经更新过 token 了，
        短时间内直接请求 API 即可，不需要再 get_token。
        :param doc: Mongodb 文档
        :param update_token: 是否更新 token。如果不需要请求任何 API，token 没必要更新
        :return:
        """
        drive = MyDrive(app_id=doc.get('app_id'),
                        token=doc.get('token'),
                        config_obj=Configs(doc.get('config') or {}))

        if update_token:
            drive.get_token()

        return drive

    @staticmethod
    def create_from_app_id(app_id):
        doc = mongodb.drive.find_one({'app_id': app_id}) or {}
        return MyDrive.create(doc)


class RefreshTimer:
    # TODO 重写。不需要12天刷新一次，每天固定时间增量更新即可
    refresh_interval = 12  # days
    timers = {}
    timers_data = {}

    @staticmethod
    def start_a_timer(app_id):
        timer = threading.Timer(Utils.get_seconds(RefreshTimer.refresh_interval),
                                RefreshTimer.refresh_token, (app_id,))
        timer.name = 'Timer-RefreshToken'
        timer.start()
        RefreshTimer.timers[app_id] = timer
        RefreshTimer.timers_data[app_id] = {
            'lastRefreshTime': Utils.str_datetime_now(),
            'nextRefreshTime': Utils.str_datetime_delta(days=RefreshTimer.refresh_interval)
        }

    @staticmethod
    def refresh_token(app_id):
        if MyDrive.create_from_app_id(app_id).token is None:
            RefreshTimer.stop(app_id)
        else:
            RefreshTimer.start_a_timer(app_id)

    @staticmethod
    def start(app_id):
        timer = RefreshTimer.timers.get(app_id)
        if isinstance(timer, threading.Timer) and timer.is_alive():
            return

        RefreshTimer.start_a_timer(app_id)
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


def update_config(app_id, config, add_if_not_exist=False):
    """
    初始化或更新配置项
    :param app_id:
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
            complete_k = 'config.{}.{}'.format(k, _k)

            query = {
                'app_id': app_id,
                complete_k: {'$exists': not add_if_not_exist}
            }

            modified_count = mongodb.drive.update_one(
                query, {'$set': {complete_k: _v}}).modified_count
            if modified_count == 1:
                # modified_count 等于 1 说明更新了 key 对应的配置
                res1[_k] = modified_count
        if res1:
            res[k] = res1
    return res


def init():
    # 清空 auth_temp
    mongodb.auth_temp.delete_many({})

    default_configs = Configs.create(DEFAULT_CONFIG_PATH).default()

    # drive相关
    for drive in MyDrive.drives():
        # 初始化默认配置
        update_config(drive.app_id, default_configs, add_if_not_exist=True)

        # 更新文件
        threading.Timer(1, drive.update_items).start()

        # 开启自动刷新token
        RefreshTimer.start(drive.app_id)


init()
