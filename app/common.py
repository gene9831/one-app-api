# -*- coding: utf-8 -*-
import datetime


class CURDCounter:
    def __init__(self, added=0, updated=0, deleted=0):
        self.added = added
        self.updated = updated
        self.deleted = deleted

    def detail(self):
        if self.count() > 0:
            return '{0} added, {1} updated, {2} deleted'.format(self.added,
                                                                self.updated,
                                                                self.deleted)
        return 'nothing changed'

    def merge(self, counter):
        self.added += counter.added
        self.updated += counter.updated
        self.deleted += counter.deleted

    def count(self):
        return self.added + self.updated + self.deleted

    def json(self):
        return self.__dict__.copy()


class Utils:
    DEFAULT_DATETIME_FMT = '%Y-%m-%d %H:%M:%S'

    @staticmethod
    def str_datetime_now(fmt: str = DEFAULT_DATETIME_FMT) -> str:
        return datetime.datetime.now().strftime(fmt)

    @staticmethod
    def path_with_slash(path: str, start=True, end=False, root=True):
        """
        默认以'/'开头，结尾不带'/'。
        根目录为'/'，如果root为False，则根目录是空字符''
        :param path:
        :param start:
        :param end:
        :param root:
        :return:
        """
        new_path = path.strip('/')
        if start:
            new_path = '/' + new_path
        if end:
            if new_path != '/':
                # 防止出现两个连续'/'
                new_path = new_path + '/'
        if not root and new_path == '/':
            new_path = ''
        return new_path

    @staticmethod
    def path_join(path1: str, path2: str, root=True):
        """
        合并两个 path，以’/'开头，结尾不带'/'
        根目录为'/'，如果root为False，则根目录是空字符''
        :param path1:
        :param path2:
        :param root:
        :return:
        """
        return Utils.path_with_slash(
            Utils.path_with_slash(
                path1
            ) + Utils.path_with_slash(
                path2, root=False
            ), root=root)
