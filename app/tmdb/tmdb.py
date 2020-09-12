# -*- coding: utf-8 -*-

from requests import sessions


class TMDb:
    api_base_url = 'https://api.themoviedb.org/3'
    image_url = 'https://image.tmdb.org/t/p'
    image_original_url = '{}/original'.format(image_url)

    def __init__(self):
        self.session = sessions.Session()

    def movie(self, movie_id, params=None):
        res = self.session.get('{}/movie/{}'.format(self.api_base_url, movie_id), params=params)
        return res.json()

    def search(self, query, year):
        params = {'query': query, 'year': year}

        res = self.session.get('{}/search/movie'.format(self.api_base_url), params=params)
        return res.json()
