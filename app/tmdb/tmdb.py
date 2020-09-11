# -*- coding: utf-8 -*-

from requests import sessions


class TMDb:
    api_base_url = 'https://api.themoviedb.org/3'
    image_url = 'https://image.tmdb.org/t/p'
    image_original_url = '{}/original'.format(image_url)

    session = sessions.Session()

    @classmethod
    def set_session(cls, **kwargs):
        cls.session.params.clear()
        cls.session.proxies.clear()

        if isinstance(kwargs.get('params'), dict):
            cls.session.params.update(kwargs.get('params'))

    @classmethod
    def movie(cls, movie_id, params=None):
        cls.set_session(params=params)

        res = cls.session.get('{}/movie/{}'.format(cls.api_base_url, movie_id))
        return res.json()

    @classmethod
    def search(cls, query, year):
        params = {'query': query, 'year': year}
        cls.set_session(params=params)

        res = cls.session.get('{}/search/movie'.format(cls.api_base_url))
        return res.json()
