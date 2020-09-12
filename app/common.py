# -*- coding: utf-8 -*-
import datetime

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
        minimal = kwargs.get('minimal') or False
        self.value = kwargs.get('value')
        if minimal is False or kwargs.get('type') is not None:
            self.type = kwargs.get('type') or 'str'
        if minimal is False or kwargs.get('field') is not None:
            self.field = kwargs.get('field') or ''
        if minimal is False or kwargs.get('comment') is not None:
            self.comment = kwargs.get('comment') or ''
        if minimal is False or kwargs.get('secret') is not None:
            self.secret = kwargs.get('secret') or False  # 默认值 False
        # self.editable = kwargs.get('editable') or kwargs.get('editable') is None  # 默认值 True

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
    MiniMal = 'minimal'

    @staticmethod
    def gen(_dict: dict, _type=Detail):
        if not (_type == Configs.Detail or _type == Configs.Clarify or
                _type == Configs.Sensitive or _type == Configs.MiniMal):
            return {}

        configs = {}

        if _type == Configs.Clarify:
            for k, v in _dict.items():
                if not isinstance(v, dict):
                    continue
                v = ConfigItem(**v).json()
                field = v['field']
                if field:
                    if configs.get(field) is None:
                        configs[field] = {}
                    configs[field].update({k: v['value']})
                else:
                    configs.update({k: v['value']})
            return configs

        for k, v in _dict.items():
            if not isinstance(v, dict):
                continue
            if _type == Configs.Detail:
                configs[k] = ConfigItem(**v).json()
            elif _type == Configs.Sensitive:
                configs[k] = ConfigItem(**v).sensitive()
            elif _type == Configs.MiniMal:
                configs[k] = ConfigItem(**v, minimal=True).json()
        return configs

    @staticmethod
    def detail(_dict):
        return Configs.gen(_dict, _type=Configs.Detail)

    @staticmethod
    def clarify(_dict):
        return Configs.gen(_dict, _type=Configs.Clarify)

    @staticmethod
    def sensitive(_dict):
        return Configs.gen(_dict, _type=Configs.Sensitive)

    @staticmethod
    def minimal(_dict):
        return Configs.gen(_dict, _type=Configs.MiniMal)


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
