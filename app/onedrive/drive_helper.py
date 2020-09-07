# -*- coding: utf-8 -*-
from requests_oauthlib import OAuth2Session
from requests.exceptions import ConnectionError
import logging

logger = logging.getLogger(__name__)


class Url:
    drive = 'https://graph.microsoft.com/v1.0/me/drive'
    root = '{}/root'.format(drive)
    items = '{}/items'.format(drive)


def graph_client_request(graph_client, method, url, try_times=3,
                         params=None, data=None, headers=None,
                         files=None, timeout=None, json=None):
    res = None
    while try_times > 0 and res is None:
        try:
            res = graph_client.request(method, url,
                                       params=params, data=data, headers=headers,
                                       files=files, timeout=timeout, json=json)
        except ConnectionError as e:
            logger.error(e)
        try_times -= 1
    return res


class Drive:
    @staticmethod
    def delta(auth, url=None):
        graph_client = OAuth2Session(token=auth.get_token())

        if url is None:
            url = '{}/delta'.format(Url.root)

        data = {'@odata.nextLink': url}
        while '@odata.nextLink' in data.keys():
            data = graph_client.get(data['@odata.nextLink']).json()
        yield data

    @staticmethod
    def item(auth, item_id):
        graph_client = OAuth2Session(token=auth.get_token())

        return graph_client.get('{}/{}'.format(Url.items, item_id)).json()

    @staticmethod
    def create_link(auth, item_id):
        graph_client = OAuth2Session(token=auth.get_token())

        data = {'type': 'view', 'scope': 'anonymous'}
        res = graph_client.post('{}/{}/createLink'.format(Url.items, item_id), json=data)
        return res.json()['link']['webUrl']

    @staticmethod
    def content(auth, item_id):
        graph_client = OAuth2Session(token=auth.get_token())

        res = graph_client.get('{}/{}/content'.format(Url.items, item_id), allow_redirects=False)
        location = res.headers.get('Location')
        return location
    # def create_link(auth,item):
    #     base_down_url = Cache.get_base_down_url()
    #     if base_down_url is None:
    #         tmp_url = self.get_download_url(item['id'])
    #         symbol = 'download.aspx?'
    #         base_down_url = tmp_url[:tmp_url.find(symbol) + len(symbol)] + 'share='
    #         Cache.set_base_down_url(base_down_url)
    #
    #     data = {'type': 'view', 'scope': 'anonymous'}
    #     res = self.graph_client.post('{0}/items/{1}/createLink'.format(drive_url, item['id']), json=data)
    #
    #     web_url = res.json()['link']['webUrl']
    #     index = web_url.rfind('/') + 1
    #     url = base_down_url + web_url[index:]
    #
    #     return url
