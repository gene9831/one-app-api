# -*- coding: utf-8 -*-
import logging
import os
import time

import yaml
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session

# This is necessary for testing with non-HTTPS localhost
# Remove this if deploying to production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# This is necessary because Azure does not guarantee
# to return scopes in the same case and order as requested
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

project_dir, project_module_name = os.path.split(
    os.path.dirname(os.path.realpath(__file__)))
CURRENT_PATH = os.path.join(project_dir, project_module_name)

logger = logging.getLogger(__name__)

# Load the oauth_settings.yml file
with open(os.path.join(CURRENT_PATH, 'oauth_settings.yml'), 'r') as f:
    settings = yaml.load(f, yaml.SafeLoader)
authorize_url = '{0}{1}'.format(settings['authority'],
                                settings['authorize_endpoint'])
token_url = '{0}{1}'.format(settings['authority'], settings['token_endpoint'])


def get_sign_in_url():
    """
    Method to generate a sign-in url
    :return:
    """
    aad_auth = OAuth2Session(client_id=settings['app_id'],
                             scope=settings['scopes'],
                             redirect_uri=settings['redirect'])

    sign_in_url, state = aad_auth.authorization_url(authorize_url,
                                                    prompt='login')

    return sign_in_url, state


def get_token_from_code(callback_url, expected_state):
    """
    Method to exchange auth code for access token
    :param callback_url:
    :param expected_state:
    :return:
    """
    aad_auth = OAuth2Session(client_id=settings['app_id'],
                             state=expected_state,
                             scope=settings['scopes'],
                             redirect_uri=settings['redirect'])

    token = aad_auth.fetch_token(token_url,
                                 client_secret=settings['app_secret'],
                                 authorization_response=callback_url)

    return token


def refresh_token(token):
    if token is None:
        return None

    # Check expiration
    now = time.time()
    # Subtract 5 minutes from expiration to account for clock skew
    expire_time = token['expires_at'] - 300

    if now < expire_time:
        return token

    # Refresh the token
    aad_auth = OAuth2Session(client_id=settings['app_id'],
                             token=token,
                             scope=settings['scopes'],
                             redirect_uri=settings['redirect'])
    refresh_params = {
        'client_id': settings['app_id'],
        'client_secret': settings['app_secret'],
    }
    new_token = None
    try:
        # 如果token超过14天，或者id、secret已失效，会抛出异常
        new_token = aad_auth.refresh_token(token_url, **refresh_params)
    except OAuth2Error as e:
        logger.error(e)

    return new_token
