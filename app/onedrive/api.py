# -*- coding: utf-8 -*-
import logging
import threading

from flask import Blueprint, request, redirect, abort
from flask_jsonrpc import JSONRPCBlueprint
from flask_jsonrpc.exceptions import JSONRPCError, InvalidRequestError, InvalidParamsError

from . import mongodb, RefreshTimer, MyDrive
from ..common import AuthorizationSite, CURDCounter

logger = logging.getLogger(__name__)

onedrive = JSONRPCBlueprint('onedrive', __name__)
onedrive_admin = JSONRPCBlueprint('onedrive_admin', __name__, jsonrpc_site=AuthorizationSite)
onedrive_route = Blueprint('onedrive_callback', __name__)


# -------- onedrive blueprint -------- #
@onedrive.method('Onedrive.getItems')
def get_items(page: int = 1, limit: int = 20) -> list:
    skip = (page - 1) * limit
    docs = []

    for drive in MyDrive.drives(verify=False):
        query = {
            'parentReference.driveId': drive.drive_id,
            'parentReference.path': {'$regex': '^' + drive.root_path}
        }
        for doc in mongodb.item.find(query).skip(skip).limit(limit):
            doc.pop('_id', None)
            docs.append(doc)
    return docs


@onedrive.method('Onedrive.getItem')
def get_item(item_id: str) -> dict:
    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        raise InvalidParamsError(data={'message': 'Cannot find item'})
    doc.pop('_id', None)
    return doc


@onedrive.method('Onedrive.getItemContent')
def get_item_content(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(data={'message': 'You cannot get content for a folder'})

    drive_id = doc['parentReference']['driveId']
    drive = MyDrive.create_from_drive_id(drive_id)
    return drive.content(item_id)


# -------- onedrive_admin blueprint -------- #
@onedrive_admin.method('Onedrive.signIn')
def sign_in(app_id: str, app_secret: str, redirect_url: str) -> str:
    doc = mongodb.drive.find_one({'app_id': app_id})
    if doc and doc.get('token'):
        raise JSONRPCError(data={'message': 'repeat sign in'})

    drive = MyDrive(app_id, app_secret, redirect_url)
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


@onedrive_admin.method('Onedrive.getSharedItemLink')
def get_item_shared_link(item_id: str) -> str:
    doc = get_item(item_id)

    if 'folder' in doc.keys():
        raise InvalidRequestError(data={'message': 'You cannot get link for a folder'})

    if 'link' in doc.keys():
        return doc['link']

    drive_id = doc['parentReference']['driveId']
    drive = MyDrive.create_from_drive_id(drive_id)
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


@onedrive_admin.method('Onedrive.updateItems')
def update_items() -> dict:
    counter = CURDCounter()
    for drive in MyDrive.drives():
        counter.merge(drive.update_items())
    return counter.json()


@onedrive_admin.method('Onedrive.deleteItems')
def delete_items(app_id: str = None) -> dict:
    _set = {
        'drive_id': None,
        'delta_link': None,
    }

    if app_id:
        doc = mongodb.drive.find_one({'app_id': app_id})
        if doc is None:
            raise InvalidParamsError(data={'message': 'Cannot find drive'})
        mongodb.drive.update_one({'app_id': app_id}, {'$set': _set})
        count = mongodb.item.delete_many({'parentReference.driveId': doc['drive_id']}).deleted_count
        counter = CURDCounter(deleted=count)
        logger.info('app_id({}) delete items: {}'.format(doc['app_id'], counter.detail()))
        return counter.json()

    delete_count = 0
    for drive in MyDrive.drives(verify=False):
        mongodb.drive.update_one({'app_id': drive.app_id}, {'$set': _set})
        delete_count += mongodb.item.delete_many({'parentReference.driveId': drive.drive_id}).deleted_count

    counter = CURDCounter(deleted=delete_count)
    logger.info('delete all items: {}'.format(counter.detail()))
    # clean up
    mongodb.item.delete_many({})

    return counter.json()


@onedrive_admin.method('Onedrive.dropAll')
def drop_all() -> bool:
    mongodb.auth_temp.drop()
    mongodb.drive.drop()
    mongodb.item.drop()
    return True


@onedrive_admin.method('Onedrive.getDrives')
def get_drives() -> list:
    data = []
    for doc in mongodb.drive.find():
        doc.pop('_id', None)
        doc.pop('app_secret', None)
        doc.pop('token', None)
        data.append(doc)
    return data


@onedrive_admin.method('Onedrive.setDrivesConfig')
def set_drives_config(app_id: str, config: dict) -> dict:
    res = {}
    for k, v in config.items():
        res[k] = mongodb.drive.update_one({'app_id': app_id}, {'$set': {k: v}}).matched_count
    return res


@onedrive_admin.method('Onedrive.showTimers')
def show_timers() -> dict:
    return RefreshTimer.show()


# -------- onedrive_route blueprint -------- #
@onedrive_route.route('/callback', methods=['GET'])
def callback():
    state = request.args['state']
    doc = mongodb.auth_temp.find_one({'state': state})
    if doc is None:
        return {'message': 'login timeout'}
    drive = MyDrive(doc['app_id'], doc['app_secret'], doc['redirect_url'])
    token = drive.get_token_from_code(request.url, state)

    if token:
        logger.info('app_id({}) is authed'.format(drive.app_id))
        threading.Timer(1, drive.update_items).start()
        RefreshTimer.start(drive.app_id)
        return {'message': 'login successful'}
    return {'message': 'login failed'}


@onedrive_route.route('/<item_id>/<name>', methods=['GET'])
def item_content(item_id, name):
    if mongodb.item.find_one({'id': item_id, 'name': name}) is None:
        abort(404)
    content_url = get_item_content(item_id)
    return redirect(content_url)
# -------- end of blueprint -------- #
