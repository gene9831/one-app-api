# -*- coding: utf-8 -*-
import logging
import threading
from typing import Union

from app import jsonrpc_bp
from .. import MDrive, mongodb

logger = logging.getLogger(__name__)


@jsonrpc_bp.method('Onedrive.getSignInUrl', require_auth=True)
def get_sign_in_url() -> str:
    sign_in_url, state = MDrive.get_sign_in_url()
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
def put_callback_url(url: str) -> dict:
    from urllib import parse
    params = parse.parse_qs(parse.urlparse(url).query)
    states = params.get('state')
    if states is None:
        # url错误
        return {'code': 1, 'message': 'URL错误'}
    state = states[0]

    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        # 登录超时
        return {'code': 2, 'message': '登录超时'}

    mongodb.auth_temp.delete_one({'state': state})

    drive = MDrive()
    # token更新后会自动写入数据库，这句话直接一步到位
    token = drive.get_token_from_code(url, state)
    if token is None:
        # 未知错误
        return {'code': -1, 'message': '未知错误'}

    if drive.had_been_cached:
        # 重复登录
        return {'code': 3, 'message': '重复登录'}

    threading.Thread(target=drive.update_items).start()
    logger.info('drive({}) authed'.format(drive.id[:16]))

    return {'code': 0, 'message': '登录成功'}


@jsonrpc_bp.method('Onedrive.signOut', require_auth=True)
def sign_out(drive_ids: Union[str, list]) -> int:
    ids = []

    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    cnt = 0
    for drive_id in ids:
        mongodb.drive.delete_one({'id': drive_id})
        mongodb.drive_cache.delete_one({'id': drive_id})
        mongodb.item.delete_many({'parentReference.driveId': drive_id})
        mongodb.item_cache.delete_many({'drive_id': drive_id})
        cnt += 1

    return cnt
