# -*- coding: utf-8 -*-
import logging
import os
import threading

from app.common import CURDCounter
from app.config_helper import MConfigs
from . import onedrive_admin_bp
from .. import MDrive, mongodb

logger = logging.getLogger(__name__)


@onedrive_admin_bp.method('Onedrive.updateItems')
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


@onedrive_admin_bp.method('Onedrive.deleteItems')
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


@onedrive_admin_bp.method('Onedrive.dropAll')
def drop_all() -> int:
    mongodb.auth_temp.drop()
    mongodb.drive.drop()
    mongodb.drive_cache.drop()
    mongodb.item.drop()
    mongodb.item_cache.drop()
    return 0


@onedrive_admin_bp.method('Onedrive.getDrives')
def get_drives() -> list:
    res = []
    for drive_doc in mongodb.drive.find():
        drive_doc.pop('_id', None)
        res.append(drive_doc)
    return res


@onedrive_admin_bp.method('Onedrive.getConfig')
def get_config() -> dict:
    return MConfigs(id=MConfigs.Drive).sensitive()


@onedrive_admin_bp.method('Onedrive.setConfig')
def set_config(config: dict) -> int:
    configs_obj = MConfigs(id=MConfigs.Drive)
    return configs_obj.update_c(MConfigs(config)).modified_count


@onedrive_admin_bp.method('Onedrive.showThreads')
def show_threads() -> list:
    res = []
    for item in threading.enumerate():
        res.append(str(item))
    return res


@onedrive_admin_bp.method('Onedrive.apiTest')
def api_test(drive_id: str, method: str, url: str,
             headers: dict = None, data: dict = None) -> dict:
    drive = MDrive.create(drive_id)
    res = drive.request(method, url, data=data, headers=headers)
    return res.json()


@onedrive_admin_bp.method('Onedrive.listSysPath')
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
