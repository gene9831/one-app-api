# -*- coding: utf-8 -*-
import logging
import os
import time

import requests
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session

# This is necessary for testing with non-HTTPS localhost
# Remove this if deploying to production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# This is necessary because Azure does not guarantee
# to return scopes in the same case and order as requested
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

scopes = 'offline_access files.readWrite.all'
authority = 'https://login.microsoftonline.com/common'
authorize_endpoint = '/oauth2/v2.0/authorize'
token_endpoint = '/oauth2/v2.0/token'
authorize_url = authority + authorize_endpoint
token_url = authority + token_endpoint

drive_url = 'https://graph.microsoft.com/v1.0/me/drive'
root_url = '{}/root'.format(drive_url)
item_url = '{}/items'.format(drive_url)

logger = logging.getLogger(__name__)


class OneDrive:

    def __init__(self, app_id, app_secret, redirect_url, token=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_url = redirect_url
        self.token = token

    # Method to generate a sign-in url
    def get_sign_in_url(self):
        # Initialize the OAuth client
        aad_auth = OAuth2Session(self.app_id,
                                 scope=scopes,
                                 redirect_uri=self.redirect_url)

        sign_in_url, state = aad_auth.authorization_url(authorize_url, prompt='login')

        return sign_in_url, state

    # Method to exchange auth code for access token
    def get_token_from_code(self, callback_url, expected_state):
        # Initialize the OAuth client
        aad_auth = OAuth2Session(self.app_id,
                                 state=expected_state,
                                 scope=scopes,
                                 redirect_uri=self.redirect_url)

        token = None
        try:
            token = aad_auth.fetch_token(token_url,
                                         client_secret=self.app_secret,
                                         authorization_response=callback_url)
        except OAuth2Error as e:
            logger.error(e)

        # First get token, save it
        self.token = token
        return token

    def get_token(self, refresh_now=False):
        """
        Get token
        :param refresh_now: 为 True 则立即刷新
        :return:
        """
        token = self.token

        if token is None:
            return None

        # Check expiration
        now = time.time()
        # Subtract 5 minutes from expiration to account for clock skew
        expire_time = token['expires_at'] - 300
        if now >= expire_time or refresh_now:
            # Refresh the token
            aad_auth = OAuth2Session(self.app_id,
                                     token=self.token,
                                     scope=scopes,
                                     redirect_uri=self.redirect_url)
            refresh_params = {
                'client_id': self.app_id,
                'client_secret': self.app_secret,
            }
            token = None
            try:
                # TODO 添加尝试次数
                # 如果token超过14天，或者id、secret已失效，会抛出异常
                token = aad_auth.refresh_token(token_url, **refresh_params)
            except OAuth2Error as e:
                logger.error(e)

            self.token = token
            self.do_when_token_updated()

        return token

    def do_when_token_updated(self):
        pass

    def delta(self, url=None):
        graph_client = OAuth2Session(token=self.token)

        if not url:
            url = '{}/delta'.format(root_url)

        res = []
        data = {'@odata.nextLink': url}
        while '@odata.nextLink' in data.keys():
            # data = graph_client.get(data['@odata.nextLink']).json()
            data = self.request(graph_client, 'GET', data['@odata.nextLink']).json()
            res.append(data)
        return res

    def item(self, item_id):
        graph_client = OAuth2Session(token=self.token)

        # return graph_client.get('{}/{}'.format(item_url, item_id)).json()
        return self.request(graph_client, 'GET', '{}/{}'.format(item_url, item_id)).json()

    def create_link(self, item_id):
        graph_client = OAuth2Session(token=self.token)

        data = {'type': 'view', 'scope': 'anonymous'}
        # res = graph_client.post('{}/{}/createLink'.format(item_url, item_id), json=data)
        res = self.request(graph_client, 'POST', '{}/{}/createLink'.format(item_url, item_id), json=data)
        return res.json()['link']['webUrl']

    def content(self, item_id):
        graph_client = OAuth2Session(token=self.token)

        # res = graph_client.get('{}/{}/content'.format(item_url, item_id), allow_redirects=False)
        res = self.request(graph_client, 'GET', '{}/{}/content'.format(item_url, item_id), allow_redirects=False)
        location = res.headers.get('Location')
        return location

    @staticmethod
    def request(graph_client: OAuth2Session,
                method, url, try_times=3,
                data=None, headers=None, **kwargs):
        res = None
        while try_times > 0 and res is None:
            try:
                res = graph_client.request(method, url, data=data, headers=headers, **kwargs)
            except requests.exceptions.RequestException as e:
                if try_times == 1:
                    # 最后一次还是失败
                    raise requests.exceptions.RequestException(e)
            try_times -= 1
        return res
