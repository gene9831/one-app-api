# -*- coding: utf-8 -*-
import logging
import os
import threading
import time
import uuid

import requests
from flask_jsonrpc.exceptions import InvalidRequestError

from app.common import Utils
from . import onedrive_admin_bp
from .. import mongodb, MDrive
from ..models import UploadInfo

logger = logging.getLogger(__name__)
lock = threading.Lock()
uploading = {}


@onedrive_admin_bp.method('Onedrive.uploadFile')
def upload_file(drive_id: str, upload_path: str, file_path: str) -> int:
    """

    :param drive_id:
    :param upload_path: 上传至此目录下
    :param file_path: 本地文件路径
    :return:
    """
    upload_path = upload_path.replace('\\', '/')
    file_path = file_path.replace('\\', '/')

    if upload_path.endswith('/'):
        upload_path = upload_path[:-1]
    if file_path.endswith('/'):
        file_path = file_path[:-1]

    if os.path.isfile(file_path) is False:
        raise InvalidRequestError(
            data={'message': 'File({}) not found.'.format(file_path)})

    _, filename = os.path.split(file_path)
    uid = str(uuid.uuid1())
    upload_info = UploadInfo(uid=uid,
                             drive_id=drive_id,
                             filename=filename,
                             file_path=file_path,
                             upload_path=upload_path,
                             size=os.path.getsize(file_path),
                             created_date_time=Utils.str_datetime_now())
    mongodb.upload_info.insert_one(upload_info.json())

    UploadThread(uid).start()

    return 0


@onedrive_admin_bp.method('Onedrive.uploadFolder')
def upload_folder(drive_id: str, upload_path: str, folder_path: str) -> int:
    """
    上传文件夹下的文件，不上传嵌套的文件夹
    :param drive_id:
    :param upload_path:
    :param folder_path:
    :return:
    """
    upload_path = upload_path.replace('\\', '/')
    folder_path = folder_path.replace('\\', '/')

    if upload_path.endswith('/'):
        upload_path = upload_path[:-1]
    if folder_path.endswith('/'):
        folder_path = folder_path[:-1]

    if os.path.isdir(folder_path) is False:
        raise InvalidRequestError(
            data={'message': 'Folder({}) not found.'.format(folder_path)})

    _, folder_name = os.path.split(folder_path)
    for file in os.listdir(folder_path):
        file_path = folder_path + '/' + file
        if os.path.isfile(file_path) is False:
            continue

        uid = str(uuid.uuid1())
        upload_info = UploadInfo(uid=uid,
                                 drive_id=drive_id,
                                 filename=file,
                                 file_path=file_path,
                                 upload_path=upload_path + '/' + folder_name,
                                 size=os.path.getsize(file_path),
                                 created_date_time=Utils.str_datetime_now())
        mongodb.upload_info.insert_one(upload_info.json())

        UploadThread(uid).start()
    return 0


@onedrive_admin_bp.method('Onedrive.uploadStatus')
def upload_status(drive_id: str = None, param: str = None) -> list:
    query = {}
    if drive_id:
        query.update({'drive_id': drive_id})

    res = []
    for doc in mongodb.upload_info.find(query):
        info = UploadInfo(**doc)
        finished = info.finished == info.size
        running = info.uid in uploading.keys()

        data = info.json()
        data['running'] = running

        if param == 'running' and not running:
            continue
        elif param == 'stopped' and (running or finished):
            continue
        elif param == 'finished' and not finished:
            continue

        res.append(data)
    return res


@onedrive_admin_bp.method('Onedrive.startUpload')
def start_upload(uid: str) -> int:
    if uid in uploading.keys():
        return 1  # 已经在上传
    doc = mongodb.upload_info.find_one({'uid': uid})
    if doc is None:
        return -1  # 没有这个上传信息
    if doc.get('size') == doc.get('finished'):
        return 2  # 已经上传完成
    UploadThread(uid).start()
    return 0  # 启动成功


@onedrive_admin_bp.method('Onedrive.stopUpload')
def stop_upload(uid: str) -> int:
    thread = uploading.get(uid)
    if thread is None:
        return -1
    thread.stop()
    return 0


@onedrive_admin_bp.method('Onedrive.deleteUpload')
def delete_upload(uid: str = None, uids: list = None) -> int:
    uids = uids or []
    if uid:
        uids.append(uid)

    deleted_count = 0
    for uid in uids:
        doc = mongodb.upload_info.find_one({'uid': uid})
        threading.Thread(
            target=lambda: requests.delete(doc['upload_url']),
            name='DeleteUpload').start()
        deleted_count += mongodb.upload_info.delete_one(
            {'uid': uid}).deleted_count

    return deleted_count


class UploadThread(threading.Thread):
    def __init__(self, uid):
        super().__init__(name=uid, daemon=True)
        self.uid = uid
        self.running = True

    def stop(self):
        self.running = False
        # 提前pop，前端看起来停止了，实际上还会运行一段时间再停止
        self.pop_from_uploading()

    def put_to_uploading(self):
        lock.acquire()
        uploading[self.uid] = self
        lock.release()

    def pop_from_uploading(self):
        lock.acquire()
        uploading.pop(self.uid, None)
        lock.release()

    def run(self):
        self.put_to_uploading()

        chunk_size = 32 * 320 * 1024  # 10MB
        info = UploadInfo(**mongodb.upload_info.find_one({'uid': self.uid}))

        try:
            if not info.upload_url:
                # 创建上传会话
                drive = MDrive.create(info.drive_id)
                res_json = drive.create_upload_session(
                    info.upload_path + '/' + info.filename)
                upload_url = res_json.get('uploadUrl')
                if upload_url:
                    info.upload_url = upload_url
                else:
                    info.valid = False
                    info.error = 'Create upload session failed.'
                mongodb.upload_info.update_one({'uid': info.uid},
                                               {'$set': info.commit()})
            else:
                res_json = requests.get(info.upload_url).json()

            if 'nextExpectedRanges' not in res_json.keys():
                # upload_url失效
                info.valid = False
                info.error = 'Item not found'
                mongodb.upload_info.update_one({'uid': self.uid},
                                               {'$set': info.commit()})
                return

            info.finished = int(res_json['nextExpectedRanges'][0].split('-')[0])
            mongodb.upload_info.update_one({'uid': self.uid},
                                           {'$set': info.commit()})

            with open(info.file_path, 'rb') as f:
                f.seek(info.finished, 0)

                while self.running:
                    start_time = time.time()

                    chunk_start = f.tell()
                    chunk_end = chunk_start + chunk_size - 1

                    if chunk_end >= info.size:
                        # 从文件末尾往前 chunk_size 个字节
                        chunk_start = f.seek(-chunk_size, 2)
                        chunk_end = info.size - 1

                    headers = {
                        'Content-Length': str(chunk_size),
                        'Content-Range': 'bytes {}-{}/{}'.format(chunk_start,
                                                                 chunk_end,
                                                                 info.size)
                    }

                    data = f.read(chunk_size)
                    res = None
                    while res is None:
                        try:
                            res = requests.put(info.upload_url, headers=headers,
                                               data=data)
                            if res.status_code < 200 or res.status_code >= 300:
                                # Item not found
                                info.valid = False
                                info.error = res.text
                                mongodb.upload_info.update_one(
                                    {'uid': self.uid},
                                    {'$set': info.commit()})
                                return
                        except requests.exceptions.RequestException as e:
                            logger.error(e)

                    spend_time = time.time() - start_time
                    info.finished = chunk_end + 1
                    info.speed = int(chunk_size / spend_time)
                    info.spend_time += spend_time

                    res_json = res.json()
                    if 'id' in res_json.keys():
                        # 上传完成
                        info.finished_date_time = Utils.str_datetime_now()
                        mongodb.upload_info.update_one({'uid': self.uid},
                                                       {'$set': info.commit()})
                        logger.info('uploaded: {}'.format(res_json['id']))
                        break

                    if 'nextExpectedRanges' not in res_json.keys():
                        # 上传范围错误
                        info.valid = False
                        info.error = res.text
                        mongodb.upload_info.update_one({'uid': self.uid},
                                                       {'$set': info.commit()})
                        raise Exception(res.text)

                    mongodb.upload_info.update_one({'uid': self.uid},
                                                   {'$set': info.commit()})
        except Exception as e:
            logger.error(e)
        finally:
            self.pop_from_uploading()
            MDrive.create(info.drive_id).update_items()
