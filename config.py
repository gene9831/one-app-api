# -*- coding: utf-8 -*-
import os

current_dir = os.path.realpath(os.path.dirname(__file__))


class Config:
    POJ_DIR = current_dir

    SECRET_KEY = os.urandom(24)

    # MongoDB
    MONGO_URI = 'mongodb://one:movie@ubuntu.local:27017/one_movie'
