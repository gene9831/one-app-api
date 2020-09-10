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
        return self.__dict__


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
