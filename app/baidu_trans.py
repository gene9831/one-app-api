# -*- coding: utf-8 -*-
import hashlib
import random
import urllib.parse

import requests

from app.app_config import g_app_config

url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'

app_id = g_app_config.get('others', 'baidu_trans_app_id')
secret_key = g_app_config.get('others', 'baidu_trans_app_secret')


def baidu_trans(q='David Fincher'):
    if not app_id or not secret_key:
        return None
    from_lang = 'en'
    to_lang = 'zh'
    salt = random.randint(32768, 65536)
    sign = app_id + q + str(salt) + secret_key
    sign = hashlib.md5(sign.encode()).hexdigest()
    request_url = url + '?appid=' + app_id + '&q=' + urllib.parse.quote(
        q) + '&from=' + from_lang + '&to=' + to_lang + '&salt=' + str(
        salt) + '&sign=' + sign
    resp_json = requests.get(request_url).json()

    if 'trans_result' not in resp_json.keys():
        return None

    if len(resp_json['trans_result']) == 0:
        return None

    return resp_json['trans_result'][0]['dst']
