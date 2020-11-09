# -*- coding: utf-8 -*-
import logging
import threading
from typing import Union

from flask_jsonrpc.exceptions import JSONRPCError

from app import jsonrpc_bp
from .. import Drive, mongodb
from ..graph import auth

logger = logging.getLogger(__name__)


@jsonrpc_bp.method('Onedrive.getSignInUrl', require_auth=True)
def get_sign_in_url() -> str:
    sign_in_url, state = auth.get_sign_in_url()
    mongodb.auth_temp.insert_one({'state': state})
    # 10分钟后自动清除
    timer = threading.Timer(10 * 60,
                            lambda st: mongodb.auth_temp.delete_one(
                                {'state': st}),
                            (state,))
    timer.name = 'temp-auth-cleaner'
    timer.start()

    return sign_in_url


@jsonrpc_bp.method('Onedrive.putCallbackUrl', require_auth=True)
def put_callback_url(url: str) -> int:
    from urllib import parse
    params = parse.parse_qs(parse.urlparse(url).query)
    states = params.get('state')
    if states is None:
        # url错误
        raise JSONRPCError(message='URL错误')
    state = states[0]

    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        # 登录超时
        raise JSONRPCError(message='登录超时')

    mongodb.auth_temp.delete_one({'state': state})

    token = auth.get_token_from_code(url, state)
    if token is None:
        # 未知错误
        raise JSONRPCError(message='未知错误')

    drive = Drive.create_from_token(token)
    res = drive.store_drive()
    if res.matched_count > 0:
        # 重复登录
        raise JSONRPCError(message='重复登录')

    threading.Thread(target=drive.update, args=(True,)).start()

    return 0


@jsonrpc_bp.method('Onedrive.signOut', require_auth=True)
def sign_out(drive_ids: Union[str, list]) -> int:
    ids = []

    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    cnt = 0
    for drive_id in ids:
        Drive.create_from_id(drive_id).remove()
        cnt += 1

    return cnt
