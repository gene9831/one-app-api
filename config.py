# -*- coding: utf-8 -*-
import os


class Config:
    SECRET_KEY = os.urandom(24)

    PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

    # MongoDB
    MONGO_URI = 'mongodb://one:movie@172.25.11.128:27017/one_movie'
