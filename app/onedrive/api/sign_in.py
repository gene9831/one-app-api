# -*- coding: utf-8 -*-
import logging
import threading

from flask import request

from . import onedrive_admin_bp, onedrive_route_bp
from .. import MDrive, mongodb

logger = logging.getLogger(__name__)


@onedrive_admin_bp.method('Onedrive.getSignInUrl')
def get_sign_in_url() -> str:
    sign_in_url, state = MDrive.get_sign_in_url()
    mongodb.auth_temp.insert_one({'state': state})
    # 10分钟后自动清除
    timer = threading.Timer(10 * 60,
                            lambda st: mongodb.auth_temp.delete_one(
                                {'state': st}),
                            (state,))
    timer.name = 'RemoveTempAuth'
    timer.start()

    return sign_in_url


@onedrive_route_bp.route('/callback', methods=['GET'])
def callback():
    state = request.args['state']
    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        return {'message': 'login timeout'}

    drive = MDrive()
    # token更新后会自动写入数据库，这句话直接一步到位
    token = drive.get_token_from_code(request.url, state)
    if token is None:
        return {'message': 'token is invalid'}

    if drive.had_been_cached:
        return {'message': 'repeat sign in'}

    drive.auto_update_items()
    logger.info('drive({}) authed'.format(drive.id[:16]))

    # 仅仅是为了展示结果，你可以改成任何你想要的页面
    return {'message': 'login successful'}
