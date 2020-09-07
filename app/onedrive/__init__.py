# -*- coding: utf-8 -*-
import json
import logging
import threading

from flask import request, Blueprint
from flask_restful import Api, Resource, reqparse

from app import mongo
from app.helpers import ResponseGenerator as ResGen
from app.helpers import Status, CURDCounter
from .auth_helper import Auth
from .drive_helper import Drive

logger = logging.getLogger(__name__)

root_path = '/drive/root:'
mongodb = mongo.db

onedrive_bp = Blueprint('onedrive', __name__, url_prefix="/od")
api = Api(onedrive_bp)

authing = {}
authed = {}


class MyAuth(Auth):
    def save_token(self, token):
        super().save_token(token)

        doc = {
            'app_id': self.app_id,
            'app_secret': self.app_secret,
            'redirect_url': self.redirect_url,
            'refresh_time': self.refresh_time,
            'token': token
        }

        # upsert为True。如果查询不到，则insert
        mongodb.auth.replace_one({'app_id': self.app_id}, doc, upsert=True)
        logger.info('app_id({}) token updated'.format(self.app_id2))

        if token is None:
            logger.warning('app_id({}) token is null'.format(self.app_id2))

    def json(self):
        return {
            'app_id': self.app_id,
            'redirect_url': self.redirect_url,
            'refresh_time': self.refresh_time,
            'auth_state': self.token is not None
        }


def pop_authing(state):
    authing.pop(state, None)


class Login(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('app_id', type=str, required=True, help='app_id required.')
        parser.add_argument('app_secret', type=str, required=True, help='app_secret required.')
        parser.add_argument('redirect_url', type=str, required=True, help='redirect_url required.')
        args = parser.parse_args()

        if args['app_id'] in authed.keys():
            return ResGen(Status.ERROR, message='repeat login').json()

        auth = MyAuth(args['app_id'], args['app_secret'], args['redirect_url'])
        sign_in_url, state = auth.get_sign_in_url()

        authing[state] = auth
        # 5分钟后自动销毁
        threading.Timer(60 * 5, pop_authing, (state,)).start()

        logger.info('app_id({}) is authing'.format(args['app_id']))

        return ResGen(Status.OK,
                      sign_in_url=sign_in_url,
                      state=state
                      ).json()


class Callback(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('state', type=str, required=True, help='no expected state.')
        args = parser.parse_args()

        if args['state'] not in authing.keys():
            return ResGen(Status.ERROR, message='login timeout').json()

        auth = authing[args['state']]
        token = auth.get_token_from_code(request.url, args['state'])

        if token is not None:
            authed[auth.app_id] = auth
            logger.info('app_id({}) is authed'.format(auth.app_id2))
            return ResGen(Status.OK).json()
        else:
            return ResGen(Status.ERROR).json()


# class Authed(Resource):
#     def get(self):
#         res = {}
#         for app_id, auth in authed.items():
#             res[app_id] = auth.json()
#         return res


def full_update(app_id, auth):
    # 全量更新
    drive_id = None
    delta_link = None

    cnt_added = 0
    for data in Drive.delta(auth):
        if '@odata.deltaLink' in data:
            delta_link = data['@odata.deltaLink']

        items = data['value']
        for item in items:
            if item['@odata.type'] != '#microsoft.graph.driveItem':
                continue

            if drive_id is None:
                drive_id = item['parentReference']['driveId']
            # 有，就覆盖原来的；没有，就插入
            mongodb.item.replace_one({'id': item['id']}, item, upsert=True)
            cnt_added += 1

    mongodb.drive.replace_one({'app_id': app_id},
                              {
                                  'app_id': app_id,
                                  'drive_id': drive_id,
                                  'delta_link': delta_link
                              },
                              upsert=True)

    counter = CURDCounter(added=cnt_added)
    logger.info('app_id({}) full updated: {}'.format(auth.app_id2, counter.detail()))
    return counter


def incr_update(app_id, auth):
    # 增量更新
    doc = mongodb.drive.find_one({'app_id': app_id})
    delta_link = doc['delta_link']

    cnt_added = 0
    cnt_deleted = 0
    cnt_modified = 0

    for data in Drive.delta(auth, delta_link):
        print(json.dumps(data))
        if '@odata.deltaLink' in data:
            delta_link = data['@odata.deltaLink']

        items = data['value']
        for item in items:
            if item['@odata.type'] != '#microsoft.graph.driveItem':
                continue

            if 'deleted' in item.keys() and item['deleted'].get('state') == 'deleted':
                # 删  delete_one
                res = mongodb.item.delete_one({'id': item['id']})
                cnt_deleted += res.deleted_count
            else:
                # 增、改  replace_one
                res = mongodb.item.replace_one({'id': item['id']}, item, upsert=True)
                if res.modified_count == 1:
                    cnt_modified += 1
                else:
                    cnt_added += 1

    mongodb.drive.update_one({'app_id': app_id}, {'$set': {'delta_link': delta_link}})

    counter = CURDCounter(added=cnt_added, modified=cnt_modified, deleted=cnt_deleted)
    logger.info('app_id({}) incremental update: {}'.format(auth.app_id2, counter.detail()))
    return counter


def get_app_id_by_iem_id(item_id):
    doc = mongodb.item.find_one({'id': item_id})
    drive_id = doc['parentReference']['driveId']
    doc = mongodb.drive.find_one({'drive_id': drive_id})
    return doc['app_id']


def item_content(item_id):
    if 'folder' in mongodb.item.find_one({'id': item_id}):
        return ResGen(Status.ERROR, message='You cannot get content for a folder').json()

    app_id = get_app_id_by_iem_id(item_id)
    return ResGen(Status.OK, url=Drive.content(authed[app_id], item_id)).json()


def item_link(item_id):
    if 'folder' in mongodb.item.find_one({'id': item_id}):
        return ResGen(Status.ERROR, message='You cannot get link for a folder').json()

    doc = mongodb.item.find_one({'id': item_id})
    if doc is None:
        return ResGen(Status.ERROR, message='wrong id').json()

    doc.pop('_id', None)
    if 'link' in doc.keys():
        link = doc['link']
    else:
        app_id = get_app_id_by_iem_id(item_id)
        base_url = mongodb.drive.find_one({'app_id': app_id}).get('base_url')
        if base_url is None:
            tmp_url = Drive.content(authed[app_id], item_id)
            symbol = 'download.aspx?'
            base_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
            mongodb.drive.update_one({'app_id': app_id}, {'$set': {'base_url': base_url}})

        link = Drive.create_link(authed[app_id], item_id)
        index = link.rfind('/') + 1
        link = base_url + link[index:]
        mongodb.item.update_one({'id': item_id}, {'$set': {'link': link}})
    return ResGen(Status.OK, link=link).json()


class Items(Resource):
    def get(self, item_id1=None, item_id2=None, item_id3=None):

        # /items/<string:item_id1>
        if item_id1:
            doc = mongodb.item.find_one({'id': item_id1})
            if doc:
                doc.pop('_id', None)
                return ResGen(Status.OK, data=doc).json()
            return ResGen(Status.ERROR, message='wrong id').json()

        # /items/<string:item_id2>/content
        if item_id2:
            return item_content(item_id2)

        # /items/<string:item_id3>/link
        if item_id3:
            return item_link(item_id3)

        parser = reqparse.RequestParser()
        parser.add_argument('path', type=str)
        args = parser.parse_args()

        path = args['path']
        data = []

        if path is None:
            for doc in mongodb.item.find():
                doc.pop('_id', None)
                data.append(doc)
        else:
            if path == '/':
                path = ''
            query = {'parentReference.path': '{}{}'.format(root_path, path)}
            for doc in mongodb.item.find(query):
                doc.pop('_id', None)
                data.append(doc)

        return ResGen(Status.OK, data=data).json()

    def put(self):
        counter = CURDCounter()
        for app_id, auth in authed.items():
            counter.merge(full_update(app_id, auth))
        return ResGen(Status.OK, message=counter.detail()).json()

    def patch(self):
        counter = CURDCounter()
        for app_id, auth in authed.items():
            counter.merge(incr_update(app_id, auth))

        return ResGen(Status.OK, message=counter.detail()).json()

    def delete(self):
        parser = reqparse.RequestParser()
        parser.add_argument('app_id', type=str)
        parser.add_argument('drive_id', type=str)
        args = parser.parse_args()

        app_id = args.get('app_id')
        drive_id = args.get('drive_id')

        if app_id is not None:
            doc = mongodb.drive.find_one({'app_id': app_id})
            mongodb.drive.delete_one({'app_id': app_id})
            cnt = mongodb.item.delete_many({'parentReference.driveId': doc['drive_id']}).deleted_count

            return ResGen(Status.OK, message=CURDCounter(deleted=cnt).detail()).json()

        elif drive_id is not None:
            mongodb.drive.delete_one({'drive_id': drive_id})
            cnt = mongodb.item.delete_many({'parentReference.driveId': drive_id}).deleted_count

            return ResGen(Status.OK, message=CURDCounter(deleted=cnt).detail()).json()
        else:
            mongodb.drive.drop()
            mongodb.item.drop()
            return ResGen(Status.OK, message='all drives and items dropped').json()


class Drives(Resource):
    def get(self):
        data = []
        for doc in mongodb.drive.find():
            doc.pop('_id', None)
            data.append(doc)

        return ResGen(Status.OK, data=data).json()


def init():
    # auth相关
    query = {
        'app_id': {'$exists': True},
        'app_secret': {'$exists': True},
        'token': {'$exists': True}
    }

    for doc in mongodb.auth.find(query):
        auth = MyAuth(app_id=doc['app_id'],
                      app_secret=doc['app_secret'],
                      redirect_url=doc['redirect_url'],
                      token=doc['token'],
                      _refresh_time=doc['refresh_time'])

        token = auth.get_token()

        if token is not None:
            authed[auth.app_id] = auth
            logger.info('app_id({}) is authed from cache'.format(auth.app_id2))

    # drive和item相关
    for app_id, auth in authed.items():
        doc = mongodb.drive.find_one({'app_id': app_id})
        # 如果app_id对应的drive为空
        if doc is None:
            # 获取delta link和全部items
            full_update(app_id, auth)
        else:
            # 如果app_id对应的drive不为空，则访问delta link进行增量更新
            incr_update(app_id, auth)


init()

api.add_resource(Login, '/login')
api.add_resource(Callback, '/callback')
api.add_resource(Drives, '/drives')
api.add_resource(Items, '/items',
                 '/items/<string:item_id1>',
                 '/items/<string:item_id2>/content',
                 '/items/<string:item_id3>/link')
