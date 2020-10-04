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
