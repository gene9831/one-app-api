# -*- coding: utf-8 -*-
import logging
import os
import threading
import time
import uuid
from typing import Dict, List

import requests
from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from app.config_inst import yaml_config
from app.common import Utils
from .. import mongodb, MDrive

logger = logging.getLogger(__name__)


class UploadInfo:
    @staticmethod
    def create_from_mongo(uid: str):
        return UploadInfo(**mongodb.upload_info.find_one({'uid': uid}))

    def __init__(self,
                 uid: str,
                 drive_id: str,
                 filename: str,
                 file_path: str,
                 upload_path: str,
                 size: int,
                 created_date_time: str,
                 upload_url: str = None,
                 **kwargs):
        self.uid = uid
        self.drive_id = drive_id
        self.filename = filename
        self.file_path = file_path
        self.upload_path = upload_path
        self.size = size
        self.upload_url = upload_url
        self.created_date_time = created_date_time
        self.finished: int = kwargs.get('finished') or 0
        self.speed: int = kwargs.get('speed') or 0
        self.spend_time: float = kwargs.get('spend_time') or 0
        self.finished_date_time: str = kwargs.get('finished_date_time') or '---'
        self.status: str = kwargs.get('status') or 'pending'
        self.error = kwargs.get('error')
        # self._commit必须放到最后赋值，而且赋值只能有一次。字典对象是可更改的
        self._commit = {}

    def __setattr__(self, key, value):
        if '_commit' not in self.__dict__.keys():
            # 初始化过程，要保证self._commit变量是最后一个赋值的
            super(UploadInfo, self).__setattr__(key, value)
            return
        assert key != '_commit'
        super(UploadInfo, self).__setattr__(key, value)
        # 这里不会触发__setattr__，因为对象没有变，而是对象内容改了
        self._commit.update({key: value})

    def commit(self):
        """
        对象初始化后，对对象的变量进行的一系列赋值操作
        :return:
        """
        res = self._commit.copy()
        self._commit.clear()
        mongodb.upload_info.update_one({'uid': self.uid},
                                       {'$set': res})
        return res

    def json(self):
        res = self.__dict__.copy()
        res.pop('_commit', None)
        return res


class UploadThread(threading.Thread):
    def __init__(self, uid, thread_pool):
        super().__init__(name=uid, daemon=True)
        self.uid = uid
        self.thread_pool = thread_pool
        self.stopped = False
        self.deleted = False

    def stop(self):
        self.stopped = True

    def delete(self):
        self.deleted = True

    def pop_from_pool(self):
        self.thread_pool.pop(self.uid)

    def run(self):
        size_mb = yaml_config.get_v('onedrive_upload_chunk_size')
        size_mb = round(size_mb / 5) * 5
        size_mb = 5 if size_mb < 5 else size_mb
        size_mb = 60 if size_mb > 60 else size_mb

        chunk_size = 1024 * 1024 * size_mb
        info = UploadInfo.create_from_mongo(self.uid)

        try:
            info.status = 'running'
            info.commit()
            if not info.upload_url:
                # 创建上传会话
                drive = MDrive.create(info.drive_id)
                with threading.Lock():
                    # 创建上传会话会更新token，可能出现多个线程更新token，加个锁
                    res_json = drive.create_upload_session(
                        info.upload_path + info.filename)

                upload_url = res_json.get('uploadUrl')
                if upload_url:
                    info.upload_url = upload_url
                    info.commit()
                else:
                    raise Exception(str(res_json))
            else:
                res_json = requests.get(info.upload_url).json()

            if 'nextExpectedRanges' not in res_json.keys():
                # upload_url失效
                raise Exception(str(res_json))

            info.finished = int(res_json['nextExpectedRanges'][0].split('-')[0])
            info.commit()

            with open(info.file_path, 'rb') as f:
                f.seek(info.finished, 0)

                upload_session = requests.Session()

                while True:
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
                            res = upload_session.put(info.upload_url,
                                                     headers=headers,
                                                     data=data)
                            if res.status_code >= 500:
                                # OneDrive服务器错误，稍后继续尝试
                                res = None
                                time.sleep(5)
                            elif res.status_code >= 400:
                                # 文件未找到，因为其他原因被删除
                                raise Exception(res.text)
                            if self.deleted:
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
                        info.status = 'finished'
                        info.commit()
                        logger.info('uploaded: {}'.format(info.filename))
                        return

                    info.commit()

                    if self.stopped:
                        info.speed = 0
                        info.commit()
                        break
        except Exception as e:
            logger.error(e)
            info.status = 'error'
            info.error = str(e)
            info.commit()
        finally:
            self.pop_from_pool()
            MDrive.create(info.drive_id).update_items()


class UploadThreadPool(threading.Thread):
    def __init__(self):
        super().__init__(name='upload-thread-pool', daemon=True)
        self.pool: Dict[str, UploadThread] = {}
        self.pending: List[str] = []

    def add_task(self, uid: str):
        with threading.Lock():
            if uid not in self.pending:
                self.pending.append(uid)
                info = UploadInfo.create_from_mongo(uid)
                info.status = 'pending'
                info.commit()

    def stop_task(self, uid: str):
        with threading.Lock():
            if uid in self.pending:
                # 停止等待中的任务
                self.pending.remove(uid)
            if uid in self.pool.keys():
                # 停止运行中的任务
                self.pool[uid].stop()

    def del_task(self, uid: str):
        with threading.Lock():
            if uid in self.pending:
                # 删除等待中的任务
                self.pending.remove(uid)
            if uid in self.pool.keys():
                # 删除运行中的任务
                self.pool[uid].delete()

    def pop(self, uid):
        with threading.Lock():
            self.pool.pop(uid, None)

    def run(self):
        while True:
            with threading.Lock():
                while len(self.pending) > 0 and len(self.pool) < \
                        yaml_config.get_v('onedrive_upload_max_threads'):
                    # 有等待任务并且线程池没有满
                    uid = self.pending.pop(0)
                    if uid not in self.pool.keys():
                        thread = UploadThread(uid, self)
                        # 在这里添加入线程池，而不是在UploadThread start后
                        # 是为了保持pool同步
                        self.pool[uid] = thread
                        thread.start()

            time.sleep(1)


for init_doc in mongodb.upload_info.find({'$or': [
    {'status': 'running'},
    {'status': 'pending'}
]}):
    mongodb.upload_info.update_one({'uid': init_doc.get('uid')},
                                   {'$set': {'status': 'stopped', 'speed': 0}})

upload_pool = UploadThreadPool()
upload_pool.start()


@jsonrpc_bp.method('Onedrive.uploadFile', require_auth=True)
def upload_file(drive_id: str, upload_path: str, file_path: str) -> int:
    """

    :param drive_id:
    :param upload_path: 上传至此目录下，结尾带‘/’
    :param file_path: 本地文件路径
    :return:
    """
    upload_path = upload_path.strip().replace('\\', '/')
    file_path = file_path.strip().replace('\\', '/')

    if not upload_path.endswith('/'):
        upload_path = upload_path + '/'

    if os.path.isfile(file_path) is False:
        raise InvalidRequestError(
            data={'message': 'File({}) not found.'.format(file_path)})

    file_size = os.path.getsize(file_path)
    if file_size <= 5 * 1024 * 1024:
        return -1

    _, filename = os.path.split(file_path)
    uid = str(uuid.uuid4())
    upload_info = UploadInfo(uid=uid,
                             drive_id=drive_id,
                             filename=filename,
                             file_path=file_path,
                             upload_path=upload_path,
                             size=file_size,
                             created_date_time=Utils.str_datetime_now())
    mongodb.upload_info.insert_one(upload_info.json())

    upload_pool.add_task(uid)

    return 0


@jsonrpc_bp.method('Onedrive.uploadFolder', require_auth=True)
def upload_folder(drive_id: str, upload_path: str, folder_path: str) -> int:
    """
    上传文件夹下的文件，不上传嵌套的文件夹
    :param drive_id:
    :param upload_path: 上传至此目录下，结尾带‘/’
    :param folder_path: 上传此目录下的文件，结尾带'/'
    :return:
    """
    upload_path = upload_path.strip().replace('\\', '/')
    folder_path = folder_path.strip().replace('\\', '/')

    if not upload_path.endswith('/'):
        upload_path = upload_path + '/'
    if not folder_path.endswith('/'):
        folder_path = folder_path + '/'

    if os.path.isdir(folder_path) is False:
        raise InvalidRequestError(
            data={'message': 'Folder({}) not found.'.format(folder_path)})

    _, folder_name = os.path.split(folder_path[:-1])
    for file in sorted(os.listdir(folder_path), key=lambda x: x.lower()):
        file_path = folder_path + file
        if os.path.isfile(file_path) is False:
            continue

        file_size = os.path.getsize(file_path)
        if file_size <= 5 * 1024 * 1024:
            continue

        uid = str(uuid.uuid4())
        upload_info = UploadInfo(uid=uid,
                                 drive_id=drive_id,
                                 filename=file,
                                 file_path=file_path,
                                 upload_path=upload_path + folder_name + '/',
                                 size=file_size,
                                 created_date_time=Utils.str_datetime_now())
        mongodb.upload_info.insert_one(upload_info.json())

        upload_pool.add_task(uid)
    return 0


@jsonrpc_bp.method('Onedrive.uploadStatus', require_auth=True)
def upload_status(drive_id: str, param: str = None) -> list:
    query = {'drive_id': drive_id}

    if param == 'running':
        query.update({'$or': [
            {'status': 'running'},
            {'status': 'pending'}
        ]})
    elif param == 'stopped':
        query.update({'$or': [
            {'status': 'stopped'},
            {'status': 'error'}
        ]})
    elif param is not None:
        query.update({'status': param})

    res = []
    for doc in mongodb.upload_info.find(query):
        doc.pop('_id', None)
        doc.pop('upload_url', None)
        res.append(doc)

    return res


@jsonrpc_bp.method('Onedrive.startUpload', require_auth=True)
def start_upload(uid: str = None, uids: list = None) -> int:
    uids = uids or []
    if uid:
        uids.append(uid)

    for uid in uids:
        doc = mongodb.upload_info.find_one({'uid': uid}) or {}
        if doc.get('status') == 'stopped' or doc.get('status') == 'error':
            upload_pool.add_task(uid)

    return 0  # 启动成功


@jsonrpc_bp.method('Onedrive.stopUpload', require_auth=True)
def stop_upload(uid: str = None, uids: list = None) -> int:
    uids = uids or []
    if uid:
        uids.append(uid)

    for uid in uids:
        upload_pool.stop_task(uid)
        mongodb.upload_info.update_one(
            {'uid': uid, '$or': [{'status': 'running'}, {'status': 'pending'}]},
            {'$set': {'status': 'stopped'}})

    return 0


@jsonrpc_bp.method('Onedrive.deleteUpload', require_auth=True)
def delete_upload(uid: str = None, uids: list = None) -> int:
    uids = uids or []
    if uid:
        uids.append(uid)

    to_be_deleted = []

    for uid in uids:
        upload_pool.del_task(uid)

        doc = mongodb.upload_info.find_one({'uid': uid})
        if doc:
            to_be_deleted.append(doc.get('upload_url'))
            mongodb.upload_info.delete_one({'uid': uid})

    threading.Thread(name='DeleteUrls', target=delete_urls,
                     args=(to_be_deleted,)).start()

    return 0


def delete_urls(urls):
    for url in urls:
        try:
            requests.delete(url)
        except requests.exceptions.RequestException:
            pass
