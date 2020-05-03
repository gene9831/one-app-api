# -*- coding: utf-8 -*-
from flask import Flask
from flask_pymongo import PyMongo

mongo = PyMongo()


def create_app(config_obj):
    app = Flask(__name__)
    print(__name__)

    # 加载配置文件
    app.config.from_object(config_obj)
    print(app.config)

    mongo.init_app(app)

    from flask_restful import Api
    from app.onedrive import Login, Callback
    api = Api(app)
    api.add_resource(Login, '/login')
    api.add_resource(Callback, '/callback')

    return app

