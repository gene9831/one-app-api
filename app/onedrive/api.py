# -*- coding: utf-8 -*-
import logging
import threading

from flask import Blueprint, request, redirect, abort
from flask_jsonrpc import JSONRPCBlueprint
from flask_jsonrpc.exceptions import JSONRPCError, InvalidRequestError

from . import mongodb, RefreshTimer, MyDrive, DEFAULT_CONFIG_PATH, update_config
from ..common import AuthorizationSite, CURDCounter, Configs

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
