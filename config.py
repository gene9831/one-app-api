# -*- coding: utf-8 -*-
import os


class Config:
    SECRET_KEY = os.urandom(24)

    # MongoDB
    MONGO_URI = 'mongodb://one:movie@192.168.0.126:27017/one_movie'
