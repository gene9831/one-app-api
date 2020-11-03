# -*- coding: utf-8 -*-
import os

from app import jsonrpc_bp
from app.app_config import g_app_config


@jsonrpc_bp.method('Others.defaultLocalPath', require_auth=True)
def default_local_path() -> str:
    path = g_app_config.get('others', 'default_local_path')
    if path.startswith('~'):
        path = os.path.expanduser("~") + path[1:]
    return path.replace('\\', '/')
