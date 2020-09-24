# -*- coding: utf-8 -*-

import yaml

from app import mongo

mongodb = mongo.db


class ConfigItem:
    def __init__(self, key, **kwargs):
        self.key = key
        self.value = kwargs.get('value')
        self.type = kwargs.get('type') or 'str'
        self.field = kwargs.get('field')
        self.comment = kwargs.get('comment')
        self.secret = kwargs.get('secret') or False  # 默认值 False

    def __repr__(self):
        return self.__dict__

    def default(self, with_key=True):
        res = self.__dict__.copy()
        if with_key is False:
            res.pop('key', None)
        return res

    def sensitive(self, with_key=True):
        res = self.default(with_key=with_key)
        if self.secret:
            res['value'] = '********'
        return res


class Configs:
    @staticmethod
    def gen(_configs: dict):
        """
        生成键值对，value是 ConfigItem 对象
        :param _configs:
        :return: {key: ConfigItem}
        """
        configs = {}

        for k, v in _configs.items():
            if not isinstance(v, dict):
                continue
            configs[k] = ConfigItem(k, **v)
        return configs

    @staticmethod
    def create(yaml_file_path):
        config = {}
        with open(yaml_file_path, 'r', encoding='utf8') as f:
            config.update(yaml.load(f, Loader=yaml.FullLoader))
        return Configs(config)

    def __init__(self, configs: dict = None):
        """

        :param configs: {key: {'value': value, 'type': type, ...}}
        """
        # self.c 是一个字典 {key: ConfigItem}
        self.c = Configs.gen(configs or {})

    def default(self):
        res = {}
        for k, v in self.c.items():
            res[k] = v.default(with_key=False)
        return res

    def sensitive(self):
        """
        不显示敏感的字段值
        :return:
        """
        res = {}
        for k, v in self.c.items():
            res[k] = v.sensitive(with_key=False)
        return res

    def get_v(self, key):
        return self.c[key].value

    def set_v(self, key, value):
        self.c[key].value = value

    def get_field(self, field):
        res = {}
        for k, v in self.c.items():
            if v.field == field:
                res[k] = v.value
        return res

    def insert_c(self, configs, update=False):
        """
        不存在时插入，存在时取决于 update 的值
        :param configs:
        :param update: 如果 True，存在 key 时更新；如果 False，不进行操作
        :return:
        """
        assert isinstance(configs, Configs)
        for k, v in configs.c.items():
            if k in self.c.keys():
                if update:
                    self.c[k] = v
            else:
                self.c[k] = v

    def update_c(self, configs, insert=False):
        """
        存在时更新，不存在时取决于 insert 的值
        :param configs:
        :param insert: 如果 True，不存在 key 时插入；如果 False，不进行操作
        :return:
        """
        assert isinstance(configs, Configs)
        for k, v, in configs.c.items():
            if k in self.c.keys():
                self.c[k] = v
            else:
                if insert:
                    self.c[k] = v


class MConfigs(Configs):
    Drive = 'drive'
    TMDb = 'tmdb'

    def __init__(self, configs: dict = None, **kwargs):
        self.id = kwargs.get('id')

        configs = configs or mongodb.config.find_one({'id': self.id})

        super(MConfigs, self).__init__(configs)

    def insert_c(self, configs: Configs, update=False):
        super(MConfigs, self).insert_c(configs, update=update)
        return mongodb.config.update_one({'id': self.id},
                                         {'$set': self.default()}, upsert=True)

    def update_c(self, configs: Configs, insert=False):
        super(MConfigs, self).update_c(configs, insert=insert)
        return mongodb.config.update_one({'id': self.id},
                                         {'$set': self.default()})
