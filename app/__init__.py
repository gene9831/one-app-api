# -*- coding: utf-8 -*-
import logging

import coloredlogs
from flask import Flask, request
from flask_jsonrpc import JSONRPC, JSONRPCBlueprint
from flask_jsonrpc.exceptions import JSONRPCError
from flask_jsonrpc.site import JSONRPCSite
from flask_pymongo import PyMongo

coloredlogs.install(level='INFO')
logger = logging.getLogger(__name__)

mongo = PyMongo()


class AuthorizationSite(JSONRPCSite):
    @staticmethod
    def check_auth(req_json) -> bool:
        # TODO 换成token验证
        password = request.headers.get('X-Password')
        return password == 'secret'

    def dispatch(self, req_json):
        if not self.check_auth(req_json):
            raise JSONRPCError(message='Unauthorized',
                               data={'message': 'Unauthorized'})
        return super(AuthorizationSite, self).dispatch(req_json)


jsonrpc = JSONRPC(None, '/api')

jsonrpc_bp = JSONRPCBlueprint('blueprint', __name__)
jsonrpc_admin_bp = JSONRPCBlueprint('blueprint_admin', __name__,
                                    jsonrpc_site=AuthorizationSite)


def after_request(response):
    # 允许跨域请求
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,X-Password'
    response.headers['Access-Control-Max-Age'] = 3600
    return response


def create_app(config_obj):
    app = Flask(__name__)

    app.after_request(after_request)
    # 加载配置文件
    app.config.from_object(config_obj)
    # print(app.config)

    # MongoDB数据库初始化
    mongo.init_app(app)

    jsonrpc.init_app(app)

    from app import onedrive, tmdb, apis
    jsonrpc.register_blueprint(app, jsonrpc_bp, url_prefix='/')
    jsonrpc.register_blueprint(app, jsonrpc_admin_bp, url_prefix='/admin')

    from app.onedrive.api import onedrive_route_bp
    app.register_blueprint(onedrive_route_bp, url_prefix='/od')

    return app
