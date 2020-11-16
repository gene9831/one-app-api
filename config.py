# -*- coding: utf-8 -*-
import os


class Config:
    SECRET_KEY = os.urandom(24)

    PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

    # MongoDB
    MONGO_URI = 'mongodb://one:oneapp@127.0.0.1:27017/one_app'
