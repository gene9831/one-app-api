# -*- coding: utf-8 -*-
import coloredlogs
import logging

from flask import Flask
from flask_pymongo import PyMongo

coloredlogs.install(level='INFO')
logger = logging.getLogger(__name__)

mongo = PyMongo()


def create_app(config_obj):
    app = Flask(__name__)

    # 加载配置文件
    app.config.from_object(config_obj)
    print(app.config)

    mongo.init_app(app)

    from app.onedrive import onedrive_bp
    app.register_blueprint(onedrive_bp)

    return app
