# -*- coding: utf-8 -*-
import requests
from requests_oauthlib import OAuth2Session

drive_url = 'https://graph.microsoft.com/v1.0/me/drive'
drive_items_url = '{}/items'.format(drive_url)


class Drive:
    def __init__(self, token=None):
        self.token = token

    def get_token(self):
        return self.token

    def request(self, method, url, try_times=3, data=None, headers=None,
                **kwargs):
        client = OAuth2Session(token=self.get_token())
        res = None
        while try_times > 0 and res is None:
            try:
                res = client.request(method, url, data=data, headers=headers,
                                     **kwargs)
            except requests.exceptions.RequestException as e:
                if try_times == 1:
                    # 最后一次还是失败
                    raise requests.exceptions.RequestException(e)
            try_times -= 1
        return res

    def delta(self, url=None):
        url = url or '{}/root/delta'.format(drive_url)

        data = {'@odata.nextLink': url}
        while '@odata.nextLink' in data.keys():
            data = self.request('GET', data['@odata.nextLink']).json()
            yield data

    def drive(self):
        return self.request('GET', drive_url).json()

    def item(self, item_id):
        url = '{0}/{1}'.format(drive_items_url, item_id)

        return self.request('GET', url).json()

    def create_link(self, item_id):
        url = '{0}/{1}/createLink'.format(drive_items_url, item_id)
        data = {'type': 'view', 'scope': 'anonymous'}

        res = self.request('POST', url, json=data)
        return res.json()

    def content_url(self, item_id):
        url = '{}/{}/content'.format(drive_items_url, item_id)

        res = self.request('GET', url, allow_redirects=False)
        return res.headers.get('Location')

    def create_upload_session(self, item_path):
        url = '{}/root:{}:/createUploadSession'.format(drive_url, item_path)
        data = {
            '@microsoft.graph.conflictBehavior': 'rename',
            'name': item_path.strip().split('/')[-1]
        }

        return self.request('POST', url, json=data).json()

    def delete_permissions(self, item_id, perm_id):
        url = '{}/{}/permissions/{}'.format(drive_items_url, item_id, perm_id)

        res = self.request('DELETE', url)
        return res.status_code
