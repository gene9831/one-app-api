# -*- coding: utf-8 -*-
from enum import IntEnum


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
    def __init__(self, added=0, modified=0, deleted=0):
        self.added = added
        self.modified = modified
        self.deleted = deleted

    def detail(self):
        res = ''
        if self.added > 0:
            res += '%d added, ' % self.added
        if self.modified > 0:
            res += '%d modified, ' % self.modified
        if self.deleted > 0:
            res += '%d deleted, ' % self.deleted
        if res.endswith(', '):
            res = res[:-2]
        if res == '':
            res = 'nothing changed'
        return res

    def merge(self, mongo_result):
        self.added += mongo_result.added
        self.modified += mongo_result.modified
        self.deleted += mongo_result.deleted

    def cnt(self):
        return self.added + self.modified + self.deleted


if __name__ == '__main__':
    r = ResponseGenerator(Status.OK, data=['123', '345'])
    print(r.json())
    pass
