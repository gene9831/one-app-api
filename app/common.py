# -*- coding: utf-8 -*-
from enum import IntEnum

from flask import request
from flask_jsonrpc.exceptions import JSONRPCError
from flask_jsonrpc.site import JSONRPCSite


class Status(IntEnum):
    OK = 0
    ERROR = 1
    TIMEOUT = 2


_STATUS = ['ok', 'error', 'timeout']


class ResponseGenerator:
    def __init__(self, status_code, message=None, **kwargs):
        self.status_code = status_code
        self._message = message
        self.kwargs = kwargs

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, _message):
        self._message = _message

    def json(self):
        res = {
            'code': self.status_code.value,
            'status': _STATUS[self.status_code.value],
            'message': self._message
        }
        for k, v in self.kwargs.items():
            if v:
                res.update({k: v})
        return res


class CURDCounter:
    def __init__(self, added=0, updated=0, deleted=0):
        self.added = added
        self.updated = updated
        self.deleted = deleted

    def detail(self):
        if self.cnt() > 0:
            return '{0} added, {1} updated, {2} deleted'.format(self.added, self.updated, self.deleted)
        return 'nothing changed'

    def merge(self, counter):
        self.added += counter.added
        self.updated += counter.updated
        self.deleted += counter.deleted

    def cnt(self):
        return self.added + self.updated + self.deleted

    def json(self):
        return {
            'added': self.added,
            'updated': self.updated,
            'deleted': self.deleted
        }


class UnauthorizedError(JSONRPCError):
    code = -32800
    message = 'Unauthorized'


class AuthorizationSite(JSONRPCSite):
    def check_auth(self) -> bool:
        username = request.headers.get('X-Username')
        password = request.headers.get('X-Password')
        return username == 'username' and password == 'secret'

    def dispatch(self, req_json):
        if not self.check_auth():
            raise UnauthorizedError()
        return super(AuthorizationSite, self).dispatch(req_json)


if __name__ == '__main__':
    r = ResponseGenerator(Status.OK, data=['123', '345'])
    print(r.json())
    pass
