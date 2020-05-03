# -*- coding: utf-8 -*-
from enum import IntEnum


class Status(IntEnum):
    OK = 0
    ERROR = -1


def gen_response(status, d):
    res = d.copy()
    res['status'] = int(status)
    return res
