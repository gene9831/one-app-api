# -*- coding: utf-8 -*-

from requests import sessions


class TMDb:
    api_base_url = 'https://api.themoviedb.org/3'
    image_url = 'https://image.tmdb.org/t/p'
    image_original_url = '{}/original'.format(image_url)

    def __init__(self):
        self.session = sessions.Session()
        self.session.headers.update(
            {'Content-Type': 'application/json;charset=utf-8'})

    def movie(self, movie_id, params=None):
        res = self.session.get(
            '{}/movie/{}'.format(self.api_base_url, movie_id), params=params)
        return res.json()

    def movie_images(self, movie_id, include_image_language=''):
        params = {'include_image_language': include_image_language}
        return self.session.get(
            '{}/movie/{}/images'.format(self.api_base_url, movie_id),
            params=params).json()

    def movie_credits(self, movie_id, language='en-US'):
        params = {'language': language}
        return self.session.get(
            '{}/movie/{}/credits'.format(self.api_base_url, movie_id),
            params=params).json()

    def search_movie(self, params=None):
        res = self.session.get('{}/search/movie'.format(self.api_base_url),
                               params=params)
        return res.json()

    def collection(self, collection_id, params=None):
        return self.session.get(
            '{}/collection/{}'.format(self.api_base_url, collection_id),
            params=params
        ).json()

    def person(self, person_id, params=None):
        return self.session.get(
            '{}/person/{}'.format(self.api_base_url, person_id),
            params=params
        ).json()

    def genre_movie(self, params=None):
        res = self.session.get(
            '{}/genre/movie/list'.format(self.api_base_url), params=params)
        return res.json()
