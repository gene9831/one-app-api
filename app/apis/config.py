# -*- coding: utf-8 -*-
from typing import Any

from flask_jsonrpc.exceptions import JSONRPCError

from app import jsonrpc_bp
from app.config_inst import yaml_config


@jsonrpc_bp.method('Config.getAll', require_auth=True)
def get_all() -> dict:
    types = {}
    for key, value in yaml_config.types.items():
        types[key] = str(value)[8:-2]
    return {
        'config': yaml_config.config,
        'types': types
    }


@jsonrpc_bp.method('Config.getValue', require_auth=True)
def get_value(key: str) -> Any:
    return yaml_config.get_v(key)


@jsonrpc_bp.method('Config.setValue', require_auth=True)
def set_value(key: str, value: Any) -> int:
    res = yaml_config.set_v(key, value)
    if res == -1:
        raise JSONRPCError(message='KeyError',
                           data={'message': 'Key does not exist'})
    elif res == -2:
        raise JSONRPCError(
            message='ValueError',
            data={'message': 'the type of "{}" should be {}'.format(key, str(
                yaml_config.types[key]))})
    return 0


@jsonrpc_bp.method('Config.reload', require_auth=True)
def reload() -> int:
    yaml_config.reload()
    return 0
