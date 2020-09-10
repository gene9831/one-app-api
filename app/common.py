# -*- coding: utf-8 -*-
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


class UnauthorizedError(JSONRPCError):
    code = -32800
    message = 'Unauthorized'


class AuthorizationSite(JSONRPCSite):
    @staticmethod
    def check_auth() -> bool:
        username = request.headers.get('X-Username')
        password = request.headers.get('X-Password')
        return username == 'username' and password == 'secret'

    def dispatch(self, req_json):
        if not self.check_auth():
            raise UnauthorizedError()
        return super(AuthorizationSite, self).dispatch(req_json)
