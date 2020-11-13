# -*- coding: utf-8 -*-
import logging
import os
import threading
from typing import Union

from app import jsonrpc_bp
from app.common import CURDCounter
from .. import Drive, mongodb
from ..graph import drive_api

logger = logging.getLogger(__name__)


@jsonrpc_bp.method('Onedrive.update', require_auth=True)
def update(drive_ids: Union[str, list], entire=False) -> dict:
    ids = []

    if isinstance(drive_ids, str):
        ids.append(drive_ids)
    elif isinstance(drive_ids, list):
        ids.extend(drive_ids)

    counter = CURDCounter()
    for drive_id in ids:
        if entire:
            ct = Drive.create_from_id(drive_id).full_update()
        else:
            ct = Drive.create_from_id(drive_id).update()
        counter.merge(ct)

    return counter.json()


# @jsonrpc_bp.method('Onedrive.dropAll', require_auth=True)
def drop_all() -> int:
    mongodb.drive.drop()
    mongodb.drive_cache.drop()
    mongodb.item.drop()
    mongodb.item_cache.drop()
    return 0


@jsonrpc_bp.method('Onedrive.getDrives', require_auth=True)
def get_drives() -> list:
    res = []
    for drive_doc in mongodb.drive.find({}, {'_id': 0}):
        res.append(drive_doc)
    return res


@jsonrpc_bp.method('Onedrive.getDriveIds')
def get_drive_ids() -> list:
    res = []
    for drive_doc in mongodb.drive.find({}, {'id': 1}):
        res.append(drive_doc.get('id'))
    return res


@jsonrpc_bp.method('Onedrive.showThreads', require_auth=True)
def show_threads() -> list:
    res = []
    for item in threading.enumerate():
        res.append(str(item))
    return res


@jsonrpc_bp.method('Onedrive.apiTest', require_auth=True)
def api_test(drive_id: str, method: str, url: str, **kwargs) -> dict:
    drive = Drive.create_from_id(drive_id)
    res = drive_api.request(drive.token, method, url, **kwargs)
    return res.json()


def get_child_count(path: str) -> int:
    try:
        return len(os.listdir(path))
    except PermissionError:
        return -1


@jsonrpc_bp.method('Onedrive.listSysPath', require_auth=True)
def list_sys_path(path: str) -> list:
    if not os.path.isdir(path):
        return []

    res = []
    for file_or_dir in sorted(os.listdir(path), key=lambda x: x.lower()):
        p = os.path.join(path, file_or_dir)
        if os.path.isdir(p):
            res.append({
                'value': file_or_dir,
                'type': 'folder',
                'childCount': get_child_count(p)
            })
        elif os.path.isfile(p):
            res.append({
                'value': file_or_dir,
                'type': 'file',
                'size': os.path.getsize(p)
            })

    return res
