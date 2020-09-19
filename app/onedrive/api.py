# -*- coding: utf-8 -*-
import logging
import os
import threading
import time
import uuid

import requests
from flask import Blueprint, request, redirect, abort
from flask_jsonrpc import JSONRPCBlueprint
from flask_jsonrpc.exceptions import JSONRPCError, InvalidRequestError
from requests_oauthlib import OAuth2Session

from . import mongodb, RefreshTimer, MyDrive, DEFAULT_CONFIG_PATH, update_config
from .models import UploadInfo
from ..common import AuthorizationSite, CURDCounter, Configs, Utils

logger = logging.getLogger(__name__)

onedrive_bp = JSONRPCBlueprint('onedrive', __name__)
onedrive_admin_bp = JSONRPCBlueprint('onedrive_admin', __name__, jsonrpc_site=AuthorizationSite)
onedrive_route_bp = Blueprint('onedrive_route', __name__)


# -------- onedrive blueprint -------- #
@onedrive_bp.method('Onedrive.getMovies')
def get_movies(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []
    _or = []

    for drive in MyDrive.drives(update_token=False):
        item_id = get_item_id_by_path(drive.app_id, drive.config_obj.get_v('movies_path'))
        _or.append({'parentReference.id': item_id})

    for doc in mongodb.item.find({'$or': _or}).skip(skip).limit(limit):
        doc.pop('_id', None)
        docs.append(doc)

    return docs


@onedrive_bp.method('Onedrive.getTVSeries')
def get_tv_series(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []
    _or = []

    for drive in MyDrive.drives(update_token=False):
        item_id = get_item_id_by_path(drive.app_id, drive.config_obj.get_v('tv_series_path'))
        _or.append({'parentReference.id': item_id})

    for doc in mongodb.item.find({'$or': _or}).skip(skip).limit(limit):
        doc.pop('_id', None)
        docs.append(doc)

    return docs


@onedrive_bp.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        raise InvalidRequestError(data={'message': 'Cannot find item'})
    doc.pop('_id', None)
    return doc


@onedrive_bp.method('Onedrive.getItemContent')
def get_item_content(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(data={'message': 'You cannot get content for a folder'})

    drive = MyDrive.create_from_app_id(doc['app_id'])
    return drive.content(item_id)


# -------- onedrive_admin blueprint -------- #
@onedrive_admin_bp.method('Onedrive.getSignInUrl')
def get_sign_in_url(app_id: str, app_secret: str = None, redirect_url: str = None) -> str:
    """
    这个方法用于第一次登陆，或者当 token 失效了（token过期、app_secret已修改等原因）进行重新登陆
    :param app_id:
    :param app_secret:
    :param redirect_url:
    :return:
    """
    doc = mongodb.drive.find_one({'app_id': app_id}) or {}
    config = Configs(doc.get('config') or {})

    # 如果为空就去数据库找
    app_secret = app_secret or config.get_v('app_secret')
    redirect_url = redirect_url or config.get_v('redirect_url')
    token = doc.get('token')

    drive = MyDrive(app_id=app_id,
                    app_secret=app_secret,
                    redirect_url=redirect_url,
                    token=token)

    if drive.get_token(refresh_now=True):
        # 说明这个 app 仍然有效
        raise JSONRPCError(data={'message': 'repeat sign in. whatever, this app is still valid'})

    sign_in_url, state = drive.get_sign_in_url()

    mongodb.auth_temp.insert_one({'state': state,
                                  'app_id': app_id,
                                  'app_secret': app_secret,
                                  'redirect_url': redirect_url,
                                  })
    threading.Timer(10 * 60,
                    lambda st: mongodb.auth_temp.delete_one({'state': st}),
                    (state,)).start()
    logger.info('app_id({}) is authing'.format(app_id))
    return sign_in_url


@onedrive_admin_bp.method('Onedrive.getSharedItemLink')
def get_item_shared_link(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(data={'message': 'You cannot get link for a folder'})

    if 'link' in doc.keys():
        return doc['link']

    drive = MyDrive.create_from_app_id(doc['app_id'])
    base_down_url = mongodb.drive.find_one({'app_id': drive.app_id}).get('base_down_url')

    if base_down_url is None:
        tmp_url = drive.content(item_id)
        symbol = 'download.aspx?'
        base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
        mongodb.drive.update_one({'app_id': drive.app_id}, {'$set': {'base_down_url': base_down_url}})

    _link = drive.create_link(item_id)
    _link = base_down_url + _link[_link.rfind('/') + 1:]

    mongodb.item.update_one({'id': item_id}, {'$set': {'link': _link}})
    return _link


uploading = {}


@onedrive_admin_bp.method('Onedrive.uploadFile')
def upload_file(app_id: str, upload_path: str, file_path: str) -> dict:
    """

    :param app_id:
    :param upload_path: The directory of OneDrive which you want upload file to
    :param file_path: Local file path
    :return:
    """
    if os.path.isfile(file_path) is False:
        raise InvalidRequestError(data={'message': 'File({}) not found.'.format(file_path)})

    filename = file_path.strip().split('/')[-1]
    drive = MyDrive.create_from_app_id(app_id)
    # TODO 上传路径出错，比如没有此路径，和文件重名
    res_json = drive.create_upload_session(upload_path, filename)
    upload_url = res_json['uploadUrl']

    uid = str(uuid.uuid1())
    upload_info = UploadInfo(uid=uid,
                             filename=filename,
                             file_path=file_path,
                             upload_path=upload_path,
                             size=os.path.getsize(file_path),
                             upload_url=upload_url,
                             created_date_time=Utils.str_datetime_now())
    mongodb.upload_info.insert_one(upload_info.json())

    t = threading.Thread(None, upload, 'Upload-' + uid, (uid,), daemon=True)
    uploading[uid] = t
    t.start()

    logger.info('Start to upload file {}'.format(filename))

    return {}


def upload(uid):
    chunk_size = 32 * 320 * 1024  # 10MB

    try:
        info = UploadInfo(**mongodb.upload_info.find_one({'uid': uid}))

        res_json = requests.get(info.upload_url).json()
        if 'nextExpectedRanges' not in res_json.keys():
            # upload_url失效
            mongodb.upload_info.update_one({'uid': uid},
                                           {'$set': {'valid': False}})
            return

        finished = int(res_json['nextExpectedRanges'][0].split('-')[0])
        mongodb.upload_info.update_one({'uid': uid},
                                       {'$set': {
                                           info.FINISHED: finished,
                                       }})

        with open(info.file_path, 'rb') as f:
            f.seek(finished, 0)

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
                    'Content-Range': 'bytes {}-{}/{}'.format(chunk_start, chunk_end, info.size)
                }

                data = f.read(chunk_size)
                res = None
                while res is None:
                    try:
                        res = requests.put(info.upload_url, headers=headers, data=data)
                        if res.status_code < 200 or res.status_code >= 300:
                            logger.error(res.text)
                            res = None
                    except requests.exceptions.RequestException as e:
                        logger.error(e)

                spend_time = time.time() - start_time
                info.spend_time += spend_time
                _set = {
                    info.FINISHED: chunk_end + 1,
                    info.SPEED: int(chunk_size / spend_time),
                    info.SPEND_TIME: info.spend_time,
                }

                res_json = res.json()
                if 'id' in res_json.keys():
                    # 上传完成
                    _set[info.FINISHED_DT] = Utils.str_datetime_now()
                    mongodb.upload_info.update_one({'uid': uid},
                                                   {'$set': _set})
                    logger.info('uploaded: {}'.format(res_json['id']))
                    break

                mongodb.upload_info.update_one({'uid': uid},
                                               {'$set': _set})

    except Exception as e:
        logger.error(e)
    finally:
        uploading.pop(uid, None)


@onedrive_admin_bp.method('Onedrive.uploadStatus')
def upload_status(param: str = None) -> list:
    res = []
    for doc in mongodb.upload_info.find():
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

        data.pop('upload_url', None)
        res.append(data)
    return res


@onedrive_admin_bp.method('Onedrive.startUpload')
def start_upload(uid: str) -> int:
    if uid in uploading.keys():
        return 2  # 已经在上传
    doc = mongodb.upload_info.find_one({'uid': uid}) or {}
    if doc.get('size') == doc.get('finished'):
        return 0  # 已经上传完成
    t = threading.Thread(None, upload, 'Upload-' + uid, (uid,), daemon=True)
    uploading[uid] = t
    t.start()
    return 1  # 启动成功


@onedrive_admin_bp.method('Onedrive.apiTest')
def api_test(app_id: str, method: str, url: str,
             headers: dict = None, data: dict = None) -> dict:
    drive = MyDrive.create_from_app_id(app_id)
    graph_client = OAuth2Session(token=drive.token)
    res = MyDrive.request(graph_client, method, url, data=data, headers=headers)
    return res.json()


@onedrive_admin_bp.method('Onedrive.updateItems')
def update_items() -> dict:
    counter = CURDCounter()
    for drive in MyDrive.drives():
        counter.merge(drive.update_items())
    return counter.json()


@onedrive_admin_bp.method('Onedrive.deleteItems')
def delete_items(app_id: str = None) -> dict:
    _set = {
        'delta_link': None,
    }

    if app_id:
        doc = mongodb.drive.find_one({'app_id': app_id})
        if doc is None:
            raise InvalidRequestError(data={'message': 'Cannot find drive'})
        mongodb.drive.update_one({'app_id': app_id}, {'$set': _set})
        count = mongodb.item.delete_many({'app_id': app_id}).deleted_count
        counter = CURDCounter(deleted=count)
        logger.info('app_id({}) delete items: {}'.format(app_id, counter.detail()))
        return counter.json()

    delete_count = 0
    for drive in MyDrive.drives(update_token=False):
        mongodb.drive.update_one({'app_id': drive.app_id}, {'$set': _set})
        delete_count += mongodb.item.delete_many({'app_id': app_id}).deleted_count

    counter = CURDCounter(deleted=delete_count)
    logger.info('delete all items: {}'.format(counter.detail()))
    # clean up
    mongodb.item.delete_many({})

    return counter.json()


@onedrive_admin_bp.method('Onedrive.dropAll')
def drop_all() -> bool:
    mongodb.auth_temp.drop()
    mongodb.drive.drop()
    mongodb.item.drop()
    return True


@onedrive_admin_bp.method('Onedrive.getDrives')
def get_drives() -> list:
    res = []
    for drive in MyDrive.drives(update_token=False):
        res1 = {
            'app_id': drive.app_id,
            'config': drive.config_obj.sensitive()
        }
        res.append(res1)
    return res


@onedrive_admin_bp.method('Onedrive.setDrive')
def set_drive(app_id: str, config: dict) -> dict:
    return update_config(app_id, Configs(config).original())


@onedrive_admin_bp.method('Onedrive.showTimers')
def show_timers() -> dict:
    return RefreshTimer.show()


@onedrive_admin_bp.method('Onedrive.showThreads')
def show_threads() -> list:
    res = []
    for item in threading.enumerate():
        res.append(str(item))
    return res


# -------- onedrive_route blueprint -------- #
@onedrive_route_bp.route('/callback', methods=['GET'])
def callback():
    state = request.args['state']
    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        return {'message': 'login timeout'}

    drive = MyDrive(**doc)
    token = drive.get_token_from_code(request.url, state)

    if not token:
        # 仅仅是为了展示结果，你可以改成任何你想要的页面
        return {'message': 'login failed'}

    config_obj = Configs.create(DEFAULT_CONFIG_PATH)
    config_obj.set_v('app_secret', doc.get('app_secret'))
    config_obj.set_v('redirect_url', doc.get('redirect_url'))

    new_doc = {
        'app_id': drive.app_id,
        'config': config_obj.default(),
        'token': token
    }
    mongodb.drive.update_one({'app_id': drive.app_id}, {'$set': new_doc}, upsert=True)

    logger.info('app_id({}) is authed'.format(drive.app_id))
    threading.Timer(1, drive.update_items).start()
    RefreshTimer.start(drive.app_id)
    # 仅仅是为了展示结果，你可以改成任何你想要的页面
    return {'message': 'login successful'}


@onedrive_route_bp.route('/<item_id>/<name>', methods=['GET'])
def item_content(item_id, name):
    if mongodb.item.find_one({'id': item_id, 'name': name}) is None:
        abort(404)
    content_url = get_item_content(item_id)
    return redirect(content_url)


# -------- end of blueprint -------- #


def get_item_id_by_path(app_id: str, path: str) -> str:
    """
    如果父目录重命名，增量更新里面并不会返回子项目的数据，
    所以 parentReference.path 不能保证是有效的。
    :param app_id:
    :param path:
    :return:
    """
    dirs = path.split('/')[1:]

    doc = mongodb.item.find_one({'app_id': app_id,
                                 'root': {'$exists': True}})

    if doc is None:
        raise JSONRPCError('Cannot find the root item of app({})'.format(app_id))

    p_id = doc['id']
    for _dir in dirs:
        doc = mongodb.item.find_one({'app_id': app_id,
                                     'parentReference.id': p_id,
                                     'name': _dir})
        if doc is None:
            raise JSONRPCError('Invalid directory ({}) of app({})'.format(_dir, app_id))

        p_id = doc['id']

    return p_id
