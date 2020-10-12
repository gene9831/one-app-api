# -*- coding: utf-8 -*-

from app import mongo

mongodb = mongo.db


def init():
    from . import auth, config


init()
