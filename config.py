# -*- coding: utf-8 -*-
import os


class Config:
    SECRET_KEY = os.urandom(24)

    # MongoDB
    MONGO_URI = 'mongodb://one:movie@ubuntu.local:27017/one_movie'
