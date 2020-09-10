# -*- coding: utf-8 -*-
import os
import sys


class Config:
    PROJECT_DIR, PROJECT_MODULE_NAME = os.path.split(os.path.dirname(os.path.realpath(__file__)))

    FLASK_JSONRPC_PROJECT_DIR = os.path.join(PROJECT_DIR)
    if os.path.exists(FLASK_JSONRPC_PROJECT_DIR) and FLASK_JSONRPC_PROJECT_DIR not in sys.path:
        sys.path.append(FLASK_JSONRPC_PROJECT_DIR)

    SECRET_KEY = os.urandom(24)

    # MongoDB
    MONGO_URI = 'mongodb://one:movie@ubuntu.local:27017/one_movie'
