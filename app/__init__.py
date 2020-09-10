# -*- coding: utf-8 -*-
import logging
import os
import sys

import coloredlogs
from flask import Flask
from flask_jsonrpc import JSONRPC
from flask_pymongo import PyMongo

coloredlogs.install(level='INFO')
logger = logging.getLogger(__name__)

mongo = PyMongo()

jsonrpc = JSONRPC(None, '/api')


def create_app(config_obj):
    app = Flask(__name__)

    # 加载配置文件
    app.config.from_object(config_obj)
    # print(app.config)

    # MongoDB数据库初始化
    mongo.init_app(app)

    from app.onedrive.api import onedrive, onedrive_admin, onedrive_route
    jsonrpc.init_app(app)
    jsonrpc.register_blueprint(app, onedrive, url_prefix='/od')
    jsonrpc.register_blueprint(app, onedrive_admin, url_prefix='/admin/od')

    app.register_blueprint(onedrive_route, url_prefix='/')

    return app
