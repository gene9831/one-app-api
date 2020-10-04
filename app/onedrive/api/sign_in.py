# -*- coding: utf-8 -*-
import logging
import threading

from app import jsonrpc_admin_bp
from .. import MDrive, mongodb

logger = logging.getLogger(__name__)


@jsonrpc_admin_bp.method('Onedrive.getSignInUrl')
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


@jsonrpc_admin_bp.method('Onedrive.putCallbackUrl')
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


@jsonrpc_admin_bp.method('Onedrive.signOut')
def sign_out(drive_id: str) -> int:
    mongodb.drive.delete_one({'id': drive_id})
    mongodb.drive_cache.delete_one({'id': drive_id})
    mongodb.item.delete_many({'parentReference.driveId': drive_id})
    mongodb.item_cache.delete_many({'drive_id': drive_id})

    return 0
