# -*- coding: utf-8 -*-
import json

from flask_restful import Resource, reqparse, request

from app import mongo
from .auth_helper import Auth
from .drive_helper import Drive
import threading

temp_auth = {}
drives = {}


class MyAuth(Auth):
    def save_token(self, token):
        super().save_token(token)
        print(json.dumps(token))

        token_clc = mongo.db.token

        if token_clc.find_one({'_id': self.app_id}) is None:
            token_clc.insert_one({
                '_id': self.app_id,
                'app_secret': self.app_secret,
                'token': token
            })
        else:
            new = {'$set': {
                'app_secret': self.app_secret,
                'token': token
            }}
            token_clc.update_one({'_id': self.app_id}, new)


def destroy_temp_auth(state):
    if state in temp_auth.keys():
        temp_auth.pop(state)


class Login(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('app_id', type=str, required=True, help='app id required.')
        parser.add_argument('app_secret', type=str, required=True, help='app secret required.')
        parser.add_argument('redirect_url', type=str, required=True, help='redirect url required.')
        args = parser.parse_args()

        if args['app_id'] in drives.keys():
            return {'message': 'repeat login'}

        auth = MyAuth(args['app_id'], args['app_secret'], args['redirect_url'])
        sign_in_url, state = auth.get_sign_in_url()

        temp_auth[state] = auth
        # 5分钟后自动销毁
        threading.Timer(60 * 5, destroy_temp_auth, (state,)).start()

        return {'sign_in_url': sign_in_url, 'state': state}


class Callback(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('state', type=str, help='no expected state.')
        args = parser.parse_args()

        if args['state'] not in temp_auth.keys():
            return {'message': 'login timeout'}

        auth = temp_auth[args['state']]
        auth.get_token_from_code(request.url, args['state'])

        drive = Drive(auth)

        drives[auth.app_id] = drive

        return {'message': 'success'}


def init_drives():
    # 从mongodb中初始化drive
    token_clc = mongo.db.token

    query = {
        'app_secret': {'$exists': True},
        'token': {'$exists': True}
    }

    for item in token_clc.find(query):
        pass
