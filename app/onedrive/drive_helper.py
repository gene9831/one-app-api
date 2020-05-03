# -*- coding: utf-8 -*-
from requests_oauthlib import OAuth2Session
from .auth_helper import Auth

drive_url = 'https://graph.microsoft.com/v1.0/me/drive'


class Drive:
    def __init__(self, auth: Auth, auto_refresh=True):
        self.auth = auth

        if auto_refresh:
            self.auth.auto_refresh_token()

    def delta(self):
        if not self.auth.auth_state:
            return None

        graph_client = OAuth2Session(token=self.auth.get_token())

        data = {'@odata.nextLink': '{0}/root/delta'.format(drive_url)}
        while '@odata.nextLink' in data.keys():
            data = graph_client.get(data['@odata.nextLink']).json()
            yield data

    def item(self, item_id):
        if not self.auth.auth_state:
            return None

        graph_client = OAuth2Session(token=self.auth.get_token())

        return graph_client.get('{0}/items/{1}'.format(drive_url, item_id)).json()

    def create_link(self, item_id):
        if not self.auth.auth_state:
            return None

        graph_client = OAuth2Session(token=self.auth.get_token())

        data = {'type': 'view', 'scope': 'anonymous'}
        res = graph_client.post('{0}/items/{1}/createLink'.format(drive_url, item_id), json=data)
        return res.json()['link']['webUrl']

    # def create_link(self, item):
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
