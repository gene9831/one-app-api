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


@jsonrpc_bp.method('Admin.auth')
def auth(password: str) -> dict:
    if password != yaml_config.get_v('auth_password'):
        raise JSONRPCError(message='Unauthorized',
                           data={'message': 'Wrong password'})

    res = {'token': new_token, 'expires_at': int(time.time()) + 3600 * 24 * 14}
    mongodb.token.insert_one(res)
    return res


def delete_expired_token():
    """
    删除过期token
    :return:
    """
    to_be_deleted = []
    for doc in mongodb.token.find():
        if doc.get['expires_at'] < time.time():
            to_be_deleted.append({'token': doc['token']})

    mongodb.token.delete_many({'$or': to_be_deleted})


@jsonrpc_bp.method('Admin.verifyToken')
def verify_token(token: str) -> dict:
    # 删除过期token
    delete_expired_token()
    # 让旧token失效
    deleted_count = mongodb.token.delete_one({'token': token}).deleted_count
    if deleted_count == 0:
        raise JSONRPCError(message='TokenError',
                           data={'Token verification failed'})

    res = {'token': new_token, 'expires_at': int(time.time()) + 3600 * 24 * 14}
    mongodb.token.insert_one(res)

    return res
