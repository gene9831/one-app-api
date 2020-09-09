# -*- coding: utf-8 -*-
import logging
import threading

from flask import Blueprint, request, redirect
from flask_jsonrpc import JSONRPCBlueprint
from flask_jsonrpc.exceptions import JSONRPCError, InvalidRequestError, InvalidParamsError

from . import mongodb, root_path, AutoRefreshController, MyAuth, MyDrive
from ..common import AuthorizationSite, CURDCounter

logger = logging.getLogger(__name__)

onedrive = JSONRPCBlueprint('onedrive', __name__)
onedrive_admin = JSONRPCBlueprint('onedrive_admin', __name__, jsonrpc_site=AuthorizationSite)
onedrive_route = Blueprint('onedrive_callback', __name__)


# -------- onedrive blueprint -------- #
@onedrive.method('Onedrive.getItems')
def get_items(page: int = 1, limit: int = 20, sorter: dict = None) -> list:
    skip = (page - 1) * limit
    docs = []

    for auth in MyAuth.authed():
        query = {
            'parentReference.driveId': auth.drive_id,
            'parentReference.path': {'$regex': '^' + get_root_path(auth.app_id)}
        }
        for doc in mongodb.item.find(query).skip(skip).limit(limit):
            doc.pop('_id', None)
            docs.append(doc)
    return docs


@onedrive.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id})
    doc.pop('_id', None)
    return doc


@onedrive.method('Onedrive.getItemContent')
def get_item_content(item_id: str) -> str:
    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        raise InvalidParamsError(data={'message': 'Cannot find item'})

    if 'folder' in doc:
        raise InvalidRequestError(data={'message': 'You cannot get content for a folder'})

    app_id = get_app_id_by_item_id(item_id)
    return MyDrive.content(MyAuth.create(app_id), item_id)


@onedrive.method('Onedrive.getItemLink')
def get_item_link(item_id: str) -> str:
    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        raise InvalidParamsError(data={'message': 'Cannot find item'})

    if 'folder' in doc:
        raise InvalidRequestError(data={'message': 'You cannot get link for a folder'})

    if 'link' in doc.keys():
        return doc['link']

    app_id = get_app_id_by_item_id(item_id)
    auth = MyAuth.create(app_id)
    base_down_url = mongodb.drive.find_one({'app_id': app_id}).get('base_down_url')

    if base_down_url is None:
        tmp_url = MyDrive.content(auth, item_id)
        symbol = 'download.aspx?'
        base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
        mongodb.drive.update_one({'app_id': app_id}, {'$set': {'base_down_url': base_down_url}})

    _link = MyDrive.create_link(auth, item_id)
    _link = base_down_url + _link[_link.rfind('/') + 1:]

    mongodb.item.update_one({'id': item_id}, {'$set': {'link': _link}})
    return _link


# -------- onedrive_admin blueprint -------- #
@onedrive_admin.method('Onedrive.signIn')
def sign_in(app_id: str, app_secret: str, redirect_url: str) -> str:
    doc = mongodb.drive.find_one({'app_id': app_id})
    if doc and doc.get('token'):
        raise JSONRPCError(data={'message': 'repeat sign in'})

    auth = MyAuth(app_id, app_secret, redirect_url)
    sign_in_url, state = auth.get_sign_in_url()

    mongodb.auth_temp.insert_one({'state': state,
                                  'app_id': app_id,
                                  'app_secret': app_secret,
                                  'redirect_url': redirect_url,
                                  })
    threading.Timer(60 * 5, delete_temp_auth, (state,)).start()
    logger.info('app_id({}) is authing'.format(app_id))
    return sign_in_url


@onedrive_admin.method('Onedrive.fullUpdate')
def full_update() -> dict:
    counter = CURDCounter()
    for auth in MyAuth.authed():
        counter.merge(MyDrive.full_update(auth))
    return counter.json()


@onedrive_admin.method('Onedrive.incrUpdate')
def incr_update() -> dict:
    counter = CURDCounter()
    for auth in MyAuth.authed():
        counter.merge(MyDrive.incr_update(auth))
    return counter.json()


@onedrive_admin.method('Onedrive.deleteItems')
def delete_items(drive_id: str = None) -> dict:
    unsetter = {'$unset': {'drive_id': '',
                           'delta_link': ''}}
    ids = []
    if drive_id:
        doc = mongodb.drive.find_one({'drive_id': drive_id})
        if doc:
            ids.append({'drive_id': drive_id,
                        'app_id': doc['app_id']})
    else:
        for auth in MyAuth.authed():
            if auth.drive_id:
                ids.append({'drive_id': auth.drive_id,
                            'app_id': auth.app_id})

    deleted_count = 0
    for _id in ids:
        mongodb.drive.update_one({'drive_id': _id['drive_id']}, unsetter)
        cnt = mongodb.item.delete_many({'parentReference.driveId': _id['drive_id']}).deleted_count
        deleted_count += cnt
        logger.info('app_id({}) delete items: {}'.format(_id['app_id'], CURDCounter(deleted=cnt).detail()))

    return CURDCounter(deleted=deleted_count).json()


@onedrive_admin.method('Onedrive.getDrives')
def get_drives() -> list:
    data = []
    for doc in mongodb.drive.find():
        doc.pop('_id', None)
        doc.pop('app_secret', None)
        doc.pop('token', None)
        data.append(doc)
    return data


@onedrive_admin.method('Onedrive.setRootPath')
def set_root_path(app_id: str, path: str) -> int:
    res = mongodb.drive.update_one({'app_id': app_id}, {'$set': {'root_path': path}})
    return res.modified_count


@onedrive_admin.method('Onedrive.getRootPath')
def get_root_path(app_id: str) -> str:
    doc = mongodb.drive.find_one({'app_id': app_id})
    if 'root_path' in doc.keys():
        return doc['root_path']
    return root_path


# -------- onedrive_route blueprint -------- #
@onedrive_route.route('/callback', methods=['GET'])
def callback():
    state = request.args['state']
    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        return {'message': 'login timeout'}
    auth = MyAuth(doc['app_id'], doc['app_secret'], doc['redirect_url'])
    token = auth.get_token_from_code(request.url, state)

    if token:
        logger.info('app_id({}) is authed'.format(auth.app_id))
        AutoRefreshController.start(auth.app_id)
        return {'message': 'login successful'}
    return {'message': 'login failed'}


@onedrive_route.route('/link/<item_id>/<name>', methods=['GET'])
def link(item_id, name):
    _link = get_item_link(item_id)
    return redirect(_link)


# -------- end of blueprint -------- #

def get_app_id_by_item_id(item_id):
    doc = mongodb.item.find_one({'id': item_id})
    drive_id = doc['parentReference']['driveId']
    doc = mongodb.drive.find_one({'drive_id': drive_id})
    return doc['app_id']


def delete_temp_auth(state):
    mongodb.auth_temp.delete_one({'state': state})
