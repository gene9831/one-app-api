# -*- coding: utf-8 -*-
import os
from typing import Any

import yaml
from flask_jsonrpc.exceptions import JSONRPCError

from app import jsonrpc_admin_bp
from config import Config

CONFIG_NAME = 'config.yml'
CONFIG_BAK_NAME = 'config.bak.yml'


class YamlConfig:

    def __init__(self):
        self.config = {}
        self.types = {}

        # 加载默认配置
        path = os.path.join(Config.PROJECT_DIR, CONFIG_BAK_NAME)
        with open(path, 'r', encoding='utf8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        for key, value in config.items():
            # 如果value是None，会变成空字符串
            self.config[key] = value or ''
            self.types[key] = type(self.config[key])

        # 加载自定配置
        path = os.path.join(Config.PROJECT_DIR, CONFIG_NAME)
        if not os.path.isfile(path):
            return
        with open(path, 'r', encoding='utf8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        for key, value in config.items():
            config_value = self.config.get(key)
            if config_value is not None and type(config_value) == type(value):
                self.config[key] = value

    def __repr__(self):
        return str({
            'config': self.config,
            'types': self.types
        })

    def get_v(self, key):
        return self.config.get(key)

    def set_v(self, key, value):
        if key not in self.config.keys():
            return False
        if type(self.config[key]) != type(value):
            return False
        self.config[key] = value
        return True


yaml_config = YamlConfig()


@jsonrpc_admin_bp.method('Config.getConfig')
def get_config() -> dict:
    types = {}
    for key, value in yaml_config.types.items():
        types[key] = str(value)[8:-2]
    return {
        'config': yaml_config.config,
        'types': types
    }


@jsonrpc_admin_bp.method('Config.setConfig')
def set_config(key: str, value: Any) -> int:
    if not yaml_config.set_v(key, value):
        raise JSONRPCError(message='KeyError',
                           data={'message': 'Key does not exist'})
    return 0


@jsonrpc_admin_bp.method('Config.reload')
def reload() -> int:
    global yaml_config
    yaml_config = YamlConfig()
    return 0
