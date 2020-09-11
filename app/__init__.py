# -*- coding: utf-8 -*-
import logging

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

    jsonrpc.init_app(app)

    from app.onedrive.api import onedrive_bp, onedrive_admin_bp, onedrive_route_bp
    jsonrpc.register_blueprint(app, onedrive_bp, url_prefix='/od')
    jsonrpc.register_blueprint(app, onedrive_admin_bp, url_prefix='/admin/od')

    app.register_blueprint(onedrive_route_bp, url_prefix='/')

    from app.tmdb.api import tmdb_bp, tmdb_admin_bp
    jsonrpc.register_blueprint(app, tmdb_bp, url_prefix='/tmdb')
    jsonrpc.register_blueprint(app, tmdb_admin_bp, url_prefix='/admin/tmdb')

    return app
