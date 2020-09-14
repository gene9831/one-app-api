# -*- coding: utf-8 -*-
import datetime
import os

import yaml
from flask import request
from flask_jsonrpc.exceptions import JSONRPCError
from flask_jsonrpc.site import JSONRPCSite


class CURDCounter:
    def __init__(self, added=0, updated=0, deleted=0):
        self.added = added
        self.updated = updated
        self.deleted = deleted

    def detail(self):
        if self.count() > 0:
            return '{0} added, {1} updated, {2} deleted'.format(self.added, self.updated, self.deleted)
        return 'nothing changed'

    def merge(self, counter):
        self.added += counter.added
        self.updated += counter.updated
        self.deleted += counter.deleted

    def count(self):
        return self.added + self.updated + self.deleted

    def json(self):
        return self.__dict__.copy()


class AuthorizationSite(JSONRPCSite):
    @staticmethod
    def check_auth() -> bool:
        username = request.headers.get('X-Username')
        password = request.headers.get('X-Password')
        return username == 'username' and password == 'secret'

    def dispatch(self, req_json):
        if not self.check_auth():
            raise JSONRPCError(message='Unauthorized')
        return super(AuthorizationSite, self).dispatch(req_json)


class ConfigItem:
    def __init__(self, **kwargs):
        original = kwargs.get('original') or False
        self.value = kwargs.get('value')
        if original is False or kwargs.get('type') is not None:
            self.type = kwargs.get('type') or 'str'
        if original is False or kwargs.get('field') is not None:
            self.field = kwargs.get('field') or ''
        if original is False or kwargs.get('comment') is not None:
            self.comment = kwargs.get('comment') or ''
        if original is False or kwargs.get('secret') is not None:
            self.secret = kwargs.get('secret') or False  # 默认值 False

    def __repr__(self):
        return str(self.__dict__)

    def json(self):
        return self.__dict__.copy()

    def sensitive(self):
        res = self.json()
        if self.secret:
            res['value'] = '********'
        return res


class Configs:
    Detail = 'detail'
    Clarify = 'clarify'
    Sensitive = 'sensitive'
    Original = 'original'

    def __init__(self, config: dict):
        self._original = self.gen(config, _type=self.Original)

    def original(self):
        return self._original

    def default(self):
        """
        全部字段齐全，一般用于初始化
        :return:
        """
        return self.gen(self._original, _type=self.Detail)

    def sensitive(self):
        """
        如果 secret 为 True，value 会变成 ********
        :return:
        """
        return self.gen(self._original, _type=self.Sensitive)

    def get_v(self, key):
        if key in self._original.keys():
            return self._original[key].get('value')
        return None

    def set_v(self, key, value):
        if key in self._original.keys():
            self._original[key]['value'] = value

    def get_field(self, field):
        res = {}
        for k, v in self._original.items():
            if v.get('field') == field:
                res[k] = v.get('value')
        return res

    @staticmethod
    def gen(_dict: dict, _type=Detail):
        if not (_type == Configs.Detail or _type == Configs.Clarify or
                _type == Configs.Sensitive or _type == Configs.Original):
            return {}

        configs = {}

        for k, v in _dict.items():
            if not isinstance(v, dict):
                continue
            if _type == Configs.Detail:
                configs[k] = ConfigItem(**v).json()
            elif _type == Configs.Sensitive:
                configs[k] = ConfigItem(**v).sensitive()
            elif _type == Configs.Original:
                configs[k] = ConfigItem(**v, original=True).json()
        return configs

    @staticmethod
    def create(path):
        config = {}
        with open(os.path.join(path), encoding='utf8') as f:
            config.update(yaml.load(f, Loader=yaml.FullLoader))
        return Configs(config)


class Utils:
    @staticmethod
    def datetime_now(strf='%Y-%m-%d %H:%M'):
        return datetime.datetime.now().strftime(strf)

    @staticmethod
    def datetime_delta(strf='%Y-%m-%d %H:%M', days=0, hours=0, minutes=0):
        d = datetime.datetime.now() + datetime.timedelta(days=days, hours=hours, minutes=minutes)
        return d.strftime(strf)

    @staticmethod
    def get_seconds(day):
        return day * 24 * 3600
