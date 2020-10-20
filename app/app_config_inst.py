# -*- coding: utf-8 -*-
import json
import logging
import os
import uuid
from configparser import ConfigParser

from config import Config

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
APP_CONFIG_JSON_NAME = 'app_config.json'
APP_CONFIG_NAME = 'config.ini'

logger = logging.getLogger(__name__)


class AppConfigItem:
    def __init__(self, key, value):
        self.key = key

        if isinstance(value, (str, bool, int, float)):
            detail = {'value': value}
        elif isinstance(value, dict):
            detail = value.copy()
        else:
            detail = {}

        # "app_config" -> "App Config"
        self.name = detail.get('name') or ' '.join(
            s.capitalize() for s in key.split('_'))
        self.value = detail.get('value') or ''
        self.type = str(type(self.value))[8:-2]
        self.description = detail.get('description') or ''
        self.editable = detail.get('editable') is None or detail.get('editable')
        self.sensitive = detail.get('sensitive') or False

    def json(self, with_key=True):
        res = self.__dict__.copy()
        if not with_key:
            res.pop('key', None)
        return res

    def secret(self, with_key=True):
        res = self.json(with_key)
        if res['sensitive']:
            res['value'] = '********'
        return res

    def __repr__(self):
        return str(self.json(with_key=False))


class AppConfig:
    config_json_path = os.path.join(DIR_PATH, APP_CONFIG_JSON_NAME)
    custom_config_path = os.path.join(Config.PROJECT_DIR, APP_CONFIG_NAME)

    def __init__(self):
        self.config = {}
        self.load()

    def load(self):
        self.config.clear()
        with open(self.config_json_path, encoding='utf8') as f:
            app_config = json.load(f)
        for section, config in app_config.items():
            section_dict = {}
            for k, v in config.items():
                config_item = AppConfigItem(k, v)
                if section == 'admin' and k == 'auth_password':
                    config_item.value = str(uuid.uuid4()).replace('-', '')
                section_dict[k] = config_item
            self.config[section] = section_dict

        if os.path.exists(self.custom_config_path):
            self.load_custom()
        else:
            self.gen_config_file()

    def gen_config_file(self):
        with open(self.custom_config_path, 'w', encoding='utf8') as f:
            f.write('# 根据 app/config.json 文件自动生成的默认配置\n')
            f.write('# 可以直接修改此配置文件（请勿修改 app/config.json 文件）\n\n')
            for section, config in self.config.items():
                f.write('[{}]\n'.format(section))
                for k, v in config.items():
                    f.write('# {}: {}\n'.format(v.name, v.description))
                    f.write('{}={}\n'.format(k, v.value))
                f.write('\n')

    def reset(self):
        """
        重置内存中保存的配置
        :return:
        """
        self.load()
        return 0

    def load_custom(self):
        """
        从自定义配置文件中读取配置
        :return:
        """
        cfg = ConfigParser()
        cfg.read(self.custom_config_path, encoding='utf8')

        for section in cfg.sections():
            if section not in self.config.keys():
                continue
            for key, value in cfg.items(section):
                if key not in self.config[section].keys():
                    continue
                try:
                    cfg_value = self.config[section][key].value
                    if isinstance(cfg_value, str):
                        cfg_value = cfg.get(section, key)
                    elif isinstance(cfg_value, bool):
                        cfg_value = cfg.getboolean(section, key)
                    elif isinstance(cfg_value, int):
                        cfg_value = cfg.getint(section, key)
                    elif isinstance(cfg_value, float):
                        cfg_value = cfg.getfloat(section, key)
                    if cfg_value != self.config[section][key].value:
                        self.config[section][key].value = cfg_value
                except ValueError as e:
                    logger.error('ValueError: {}. Key: {}'.format(e, key))

    def get(self, section, key):
        config_item = (self.config.get(section) or {}).get(key)
        if config_item is None:
            return None
        return config_item.value

    def set(self, section, key, value):
        """
        修改的配置临时保存在内存中，程序重启失效。想要永久有效请修改自定义配置文件
        :param section:
        :param key:
        :param value:
        :return:
        """
        if section not in self.config.keys():
            # Section error
            return -1
        if key not in self.config[section].keys():
            # Key error
            return -2
        if not isinstance(value, type(self.config[section][key].value)):
            # Value error
            return -3
        if self.config[section][key].editable is False:
            # Permission error
            return -4
        self.config[section][key].value = value
        return 0

    def json(self):
        res = {}
        for section, config in self.config.items():
            section_dict = {}
            for k, v in config.items():
                section_dict[k] = v.json(with_key=False)
            res[section] = section_dict
        return res

    def secret(self):
        res = {}
        for section, config in self.config.items():
            section_dict = {}
            for k, v in config.items():
                section_dict[k] = v.secret(with_key=False)
            res[section] = section_dict
        return res


g_app_config = AppConfig()
