# -*- coding: utf-8 -*-
import hashlib
import time
import uuid

from flask_jsonrpc.exceptions import JSONRPCError

from app import jsonrpc_bp
from .config import yaml_config
from . import mongodb


def new_token():
    uuid_bytes = uuid.uuid4().bytes
    return hashlib.sha1(uuid_bytes).hexdigest() + hashlib.md5(
        uuid_bytes).hexdigest()


def insert_new_token():
    auth_token_max_days = 3600 * 24 * yaml_config.get_v('auth_token_max_age')
    res = {
        'token': new_token,
        'expires_at': time.time() + auth_token_max_days
    }
    mongodb.token.insert_one(res)
    return res


@jsonrpc_bp.method('Admin.auth')
def auth(password: str) -> dict:
    if password != yaml_config.get_v('auth_password'):
        raise JSONRPCError(message='Unauthorized',
                           data={'message': 'Wrong password'})

    return insert_new_token()


@jsonrpc_bp.method('Admin.validateToken')
def validate_token(token: str) -> dict:
    # 删除过期token
    mongodb.token.delete_many({'expires_at': {'$lt': time.time()}})
    # 让旧token失效
    deleted_count = mongodb.token.delete_one({'token': token}).deleted_count
    if deleted_count == 0:
        raise JSONRPCError(message='TokenError',
                           data={'Token validation failed'})

    return insert_new_token()
