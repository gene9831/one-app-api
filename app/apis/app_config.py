# -*- coding: utf-8 -*-
from typing import Any, Union

from flask_jsonrpc.exceptions import JSONRPCError

from app import jsonrpc_bp
from app.app_config import g_app_config


@jsonrpc_bp.method('AppConfig.getAll', require_auth=True)
def get_all() -> dict:
    return g_app_config.secret()


@jsonrpc_bp.method('AppConfig.get', require_auth=True)
def get_value(section: str, key: str) -> Union[str, bool, int, float, None]:
    return g_app_config.get(section, key)


@jsonrpc_bp.method('AppConfig.set', require_auth=True)
def set_value(section: str, key: str, value: Any) -> int:
    res = g_app_config.set(section, key, value)
    if res == 0:
        return 0
    elif res == -1:
        raise JSONRPCError(message='SectionError',
                           data={'message': 'section does not exist'})
    elif res == -2:
        raise JSONRPCError(message='KeyError',
                           data={'message': 'key does not exist'})
    elif res == -3:
        raise JSONRPCError(
            message='ValueError',
            data={'message': 'the type of "{}" should be {}'.format(key, type(
                g_app_config.get(section, key)))})
    elif res == -4:
        raise JSONRPCError(message='PermissionError')
    else:
        raise JSONRPCError(message='UnknownError')


@jsonrpc_bp.method('AppConfig.reset', require_auth=True)
def reset() -> int:
    g_app_config.reset()
    return 0
