# -*- coding: utf-8 -*-
import logging
import os
import threading

from app import jsonrpc_bp
from app.common import CURDCounter
from .. import MDrive, mongodb

logger = logging.getLogger(__name__)


@jsonrpc_bp.method('Onedrive.updateItems', require_auth=True)
def update_items(drive_id: str = None) -> dict:
    drives = []

    if drive_id:
        drives.append(MDrive.create(drive_id))
    else:
        for drive in MDrive.authed_drives():
            drives.append(drive)

    counter = CURDCounter()
    for drive in drives:
        ct = drive.update_items()
        counter.merge(ct)

    return counter.json()


@jsonrpc_bp.method('Onedrive.deleteItems', require_auth=True)
def delete_items(drive_id: str = None) -> dict:
    drive_ids = []

    if drive_id:
        drive_ids.append(drive_id)
    else:
        for drive in MDrive.authed_drives():
            drive_ids.append(drive.id)

    counter = CURDCounter()
    for drive_id in drive_ids:
        mongodb.drive_cache.update_one({'id': drive_id},
                                       {'$unset': {'delta_link': ''}})
        ct = CURDCounter(deleted=mongodb.item.delete_many(
            {'parentReference.driveId': drive_id}).deleted_count)
        counter.merge(ct)
        logger.info(
            'drive({}) items deleted: {}'.format(drive_id[:16], ct.detail()))

    if drive_id is None:
        # clean up
        mongodb.item.delete_many({})

    return counter.json()


@jsonrpc_bp.method('Onedrive.dropAll', require_auth=True)
def drop_all() -> int:
    mongodb.auth_temp.drop()
    mongodb.drive.drop()
    mongodb.drive_cache.drop()
    mongodb.item.drop()
    mongodb.item_cache.drop()
    return 0


@jsonrpc_bp.method('Onedrive.getDrives', require_auth=True)
def get_drives() -> list:
    res = []
    for drive_doc in mongodb.drive.find():
        drive_doc.pop('_id', None)
        res.append(drive_doc)
    return res


@jsonrpc_bp.method('Onedrive.showThreads', require_auth=True)
def show_threads() -> list:
    res = []
    for item in threading.enumerate():
        res.append(str(item))
    return res


@jsonrpc_bp.method('Onedrive.apiTest', require_auth=True)
def api_test(drive_id: str, method: str, url: str,
             headers: dict = None, data: dict = None) -> dict:
    drive = MDrive.create(drive_id)
    res = drive.request(method, url, data=data, headers=headers)
    return res.json()


@jsonrpc_bp.method('Onedrive.listSysPath', require_auth=True)
def list_sys_path(path, only_dir: bool = False) -> list:
    if not os.path.isdir(path):
        return []

    res = []
    for f_or_l in sorted(os.listdir(path), key=lambda x: x.lower()):
        if os.path.isdir(os.path.join(path, f_or_l)):
            res.append({'value': f_or_l, 'type': 'dir'})
        if not only_dir:
            if os.path.isfile(os.path.join(path, f_or_l)):
                res.append({'value': f_or_l, 'type': 'file'})

    return res
