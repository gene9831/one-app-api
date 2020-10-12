# -*- coding: utf-8 -*-
import os

import yaml

from config import Config

CONFIG_NAME = 'config.yml'
CONFIG_DEFAULT_NAME = 'config_default.yml'


class YamlConfig:

    def __init__(self):
        self.config = {}
        self.types = {}

        self.reload()

    def __repr__(self):
        return str({
            'config': self.config,
            'types': self.types
        })

    def reload(self):
        config_res = {}
        types_res = {}
        # 加载默认配置
        path = os.path.join(Config.PROJECT_DIR, CONFIG_DEFAULT_NAME)
        with open(path, 'r', encoding='utf8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        for key, value in config.items():
            # 如果value是None，会变成空字符串
            config_res[key] = value or ''
            types_res[key] = type(config_res[key])

        # 加载自定义配置
        path = os.path.join(Config.PROJECT_DIR, CONFIG_NAME)
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf8') as f:
                config = yaml.load(f, Loader=yaml.FullLoader)

            for key, value in config.items():
                config_value = config_res.get(key)
                if config_value is not None and \
                        type(config_value) == type(value):
                    config_res[key] = value

        self.config = config_res
        self.types = types_res

    def get_v(self, key):
        return self.config.get(key)

    def set_v(self, key, value):
        if key not in self.config.keys():
            return -1
        if type(self.config[key]) != type(value):
            return -2
        self.config[key] = value
        return 0


yaml_config = YamlConfig()
