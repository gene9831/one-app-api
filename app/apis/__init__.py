# -*- coding: utf-8 -*-

from app import mongo
from .config import yaml_config

mongodb = mongo.db


def init():
    from . import auth


init()
