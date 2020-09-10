# -*- coding: utf-8 -*-
import logging
import os
import time

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

logger = logging.getLogger(__name__)


class Auth:

    def __init__(self, app_id, app_secret, redirect_url,
                 token=None, drive_id=None, root_path='/drive/root:'):
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_url = redirect_url
        self.token = token
        self.drive_id = drive_id
        self.root_path = root_path

    def json(self):
        from numbers import Real
        _dict = self.__dict__
        # dictionary cannot change size during iteration. use copy()
        for k, v in _dict.copy().items():
            if not (v is None or
                    isinstance(v, (Real, str, bool, list, dict))):
                _dict.pop(k, None)
        return _dict

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
        # 如果token是None也save一下，保证数据库实时更新
        self.write_token(token)
        return token

    def write_token(self, token):
        self.token = token

    def get_token(self):
        token = self.token

        if token is None:
            return None

        # Check expiration
        now = time.time()
        # Subtract 5 minutes from expiration to account for clock skew
        expire_time = token['expires_at'] - 300
        if now >= expire_time:
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
                # 如果token超过14天，或者id、secret已失效，会抛出异常
                token = aad_auth.refresh_token(token_url, **refresh_params)
            except OAuth2Error as e:
                logger.error(e)

            self.write_token(token)

        return token


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
