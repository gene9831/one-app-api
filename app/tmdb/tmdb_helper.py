# -*- coding: utf-8 -*-
import requests
import json


class TMDb:
    base_url = 'https://api.themoviedb.org/3/'

    def __init__(self):
        self._api_key = None
        self._proxies = None

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, api_key):
        self._api_key = api_key

    @property
    def proxies(self):
        return self._proxies

    @proxies.setter
    def proxies(self, proxies):
        self._proxies = proxies


class Movie(TMDb):
    def movie(self, movie_id, params=None, **kwargs):
        params['api_key'] = self._api_key
        kwargs['proxies'] = self._proxies

        r = requests.get('{}movie/{}'.format(self.base_url, movie_id), params=params, **kwargs)
        return json.loads(r.text)

    def search(self, query, params=None, **kwargs):
        params['api_key'] = self._api_key
        kwargs['proxies'] = self._proxies
        params['query'] = query

        r = requests.get('{}search/movie'.format(self.base_url), params=params, **kwargs)
        return json.loads(r.text)
