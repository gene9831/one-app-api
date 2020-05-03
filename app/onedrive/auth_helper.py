# -*- coding: utf-8 -*-
import os
import threading
import time
import json

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


class Auth:

    def __init__(self, app_id, app_secret, redirect_url):
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_url = redirect_url

        self.token = None
        # 认证状态
        self.auth_state = False
        # 能刷新的token的最长时间为14天
        self._refresh_time = 12 * 24 * 3600  # 12 days

    @property
    def refresh_time(self):
        return self._refresh_time

    @refresh_time.setter
    def refresh_time(self, refresh_time):
        self._refresh_time = refresh_time

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

        token = aad_auth.fetch_token(token_url,
                                     client_secret=self.app_secret,
                                     authorization_response=callback_url)
        # First get token, save it
        self.save_token(token)
        self.auth_state = True
        return token

    def save_token(self, token):
        self.token = token

    def get_token(self):
        token = self.token
        if token:
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
                token = aad_auth.refresh_token(token_url, **refresh_params)
                # TODO 如果token超过14天，或者id, secret已失效，会返回什么？ 假设为None
                if token is None:
                    self.auth_state = False
                # Save new token
                self.save_token(token)

        return token

    def auto_refresh_token(self):
        self.get_token()
        print('token auto refreshed.')
        threading.Timer(self._refresh_time, self.auto_refresh_token).start()

    def set_auth_state(self, state):
        self.auth_state = state

        # TODO 可以在这里面auto refresh token
        # if self.auto_refresh:
        #     if state:
        #         # 开始自动刷新
        #         pass
        #     else:
        #         # 停止自动刷新
        #         pass
