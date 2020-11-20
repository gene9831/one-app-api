# -*- coding: utf-8 -*-
from enum import Enum
from typing import Optional, Iterator

import requests
from requests_oauthlib import OAuth2Session


class Method(Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


base_url = 'https://graph.microsoft.com/v1.0/me/drive'
items_url = '{}/items'.format(base_url)


def delta(token: dict, url: Optional[str]) -> Iterator[dict]:
    url = url or '{}/root/delta'.format(base_url)
    resp_json = {'@odata.nextLink': url}

    while '@odata.nextLink' in resp_json.keys():
        resp_json = request(token,
                            Method.GET,
                            resp_json['@odata.nextLink']
                            ).json()
        yield resp_json


def drive(token: dict) -> dict:
    return request(token, Method.GET, base_url).json()


def item(token: dict, item_id: str) -> dict:
    url = '{}/{}'.format(items_url, item_id)

    return request(token, Method.GET, url).json()


def create_link(token: dict, item_id: str,
                expiration_date_time: str = None) -> dict:
    url = '{}/{}/createLink'.format(items_url, item_id)
    data = {'type': 'view', 'scope': 'anonymous'}
    if expiration_date_time:
        data['expirationDateTime'] = expiration_date_time

    return request(token, Method.POST, url, json=data).json()


def content_url(token: dict, item_id: str) -> str:
    url = '{}/{}/content'.format(items_url, item_id)

    res = request(token, Method.GET, url, allow_redirects=False)
    return res.headers.get('Location')


def put_content(token: dict, item_path: str, data: bytes) -> dict:
    url = '{}/root:{}:/content'.format(base_url, item_path)
    return request(token, Method.PUT, url, data=data).json()


def create_upload_session(token: dict, name: str, item_path: str) -> dict:
    url = '{}/root:{}:/createUploadSession'.format(base_url, item_path)
    data = {
        '@microsoft.graph.conflictBehavior': 'rename',
        'name': name
    }

    return request(token, Method.POST, url, json=data).json()


def delete_permissions(token: dict, item_id: str, perm_id: str) -> int:
    url = '{}/{}/permissions/{}'.format(items_url, item_id, perm_id)

    res = request(token, Method.DELETE, url)
    return res.status_code


def request(token, method, url, try_times=3, data=None, headers=None,
            **kwargs):
    client = OAuth2Session(token=token)
    resp = None
    while try_times > 0 and resp is None:
        try:
            resp = client.request(method.value, url, data=data, headers=headers,
                                  **kwargs)
        except requests.exceptions.RequestException:
            if try_times == 1:
                # 最后一次还是失败
                raise
        try_times -= 1
    return resp
