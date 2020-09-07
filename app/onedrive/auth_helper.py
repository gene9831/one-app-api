# -*- coding: utf-8 -*-
import logging
import os
import threading
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

days_12 = 12


class Auth:

    def __init__(self, app_id, app_secret, redirect_url, token=None, _refresh_time=days_12):
        self.app_id = app_id
        self.app_id2 = app_id.split('-')[0]
        self.app_secret = app_secret
        self.redirect_url = redirect_url
        self.token = token
        self._refresh_time = _refresh_time  # 能刷新的token的最长时间为14天
        self.auto_refresh_timer = None

        if token:
            self.save_token(token)

    @property
    def refresh_time(self):
        return self._refresh_time

    @refresh_time.setter
    def refresh_time(self, _refresh_time):
        if _refresh_time <= days_12:
            self._refresh_time = _refresh_time
        else:
            self._refresh_time = days_12

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
        # 如果token是None也save一下，保证自动刷新的状态是正确的
        self.save_token(token)
        return token

    # 通过save_token来确定自动刷新的状态，所以写入token只用这个方法
    def save_token(self, token):
        self.token = token

        if token is not None:
            self.start_auto_refresh_token()  # 开始自动刷新
        else:
            self.stop_auto_refresh_token()  # 停止自动刷新

    def get_token(self):
        token = self.token

        if token is None:
            # 如果token是None也save一下，保证自动刷新的状态是正确的
            self.save_token(None)
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

            self.save_token(token)

        return token

    def auto_refresh_token(self):
        self.get_token()

        self.auto_refresh_timer = threading.Timer(self._refresh_time * 24 * 3600,
                                                  self.auto_refresh_token)
        self.auto_refresh_timer.start()

    def start_auto_refresh_token(self):
        # 如果是一个timer且正在运行，直接返回。否则new一个timer
        if isinstance(self.auto_refresh_timer, threading.Timer) and self.auto_refresh_timer.is_alive():
            return

        # new a timer
        logger.info('app_id({}) start auto refresh token'.format(self.app_id2))
        self.auto_refresh_timer = threading.Timer(self._refresh_time * 24 * 3600,
                                                  self.auto_refresh_token)
        self.auto_refresh_timer.start()

    def stop_auto_refresh_token(self):
        if isinstance(self.auto_refresh_timer, threading.Timer):
            logger.info('app_id({}) stop auto refresh token'.format(self.app_id2))
            self.auto_refresh_timer.cancel()
