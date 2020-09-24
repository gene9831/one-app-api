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
            return '{0} added, {1} updated, {2} deleted'.format(self.added,
                                                                self.updated,
                                                                self.deleted)
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
        password = request.headers.get('X-Password')
        return password == 'secret'

    def dispatch(self, req_json):
        if not self.check_auth():
            raise JSONRPCError(message='Unauthorized')
        return super(AuthorizationSite, self).dispatch(req_json)


class Utils:
    DEFAULT_DATETIME_FMT = '%Y-%m-%d %H:%M:%S'

    # TODO 这里有点乱七八糟的
    @staticmethod
    def str_datetime_now(fmt: str = DEFAULT_DATETIME_FMT) -> str:
        return datetime.datetime.now().strftime(fmt)

    @staticmethod
    def str_datetime_delta(fmt: str = DEFAULT_DATETIME_FMT, days=0, hours=0,
                           minutes=0) -> str:
        d = datetime.datetime.now() + datetime.timedelta(days=days, hours=hours,
                                                         minutes=minutes)
        return d.strftime(fmt)

    @staticmethod
    def datetime_delta_str(dt, fmt: str = DEFAULT_DATETIME_FMT, days=0, hours=0,
                           minutes=0):
        dt = dt + datetime.timedelta(days=days, hours=hours, minutes=minutes)
        return dt.strftime(fmt)

    @staticmethod
    def str_datetime_convert(s: str, fmt: str,
                             fmt_to: str = DEFAULT_DATETIME_FMT):
        return datetime.datetime.strptime(s, fmt).strftime(fmt_to)

    @staticmethod
    def str_to_datetime(s: str, fmt: str = DEFAULT_DATETIME_FMT):
        return datetime.datetime.strptime(s, fmt)

    @staticmethod
    def get_seconds(day):
        return day * 24 * 3600
