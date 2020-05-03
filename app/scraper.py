# -*- coding: utf-8 -*-

import re

import json
from app.tmdb import Movie

movie = Movie()
movie.api_key = ''
movie.proxies = {'http': 'http://127.0.0.1:1080', 'https': 'http://127.0.0.1:1080', }


def parse_resource_name(s):
    s = s[::-1]
    result = re.search(r'\.\d{4}\.', s)
    if result is None:
        return None, None

    return s[result.span()[1]:][::-1].replace('.', ' '), result.group()[1:-1][::-1]


def search_movie(s):
    name, year = parse_resource_name(s)
    print(name, year)
    if name is None:
        return
    r = movie.search(name, params={'year': year, })
    print(json.dumps(r))

    if r['total_results'] <= 0:
        return
    movie_id = r['results'][0]['id']
    print(movie_id)

    params = {
        'language': 'zh-CN',
        'append_to_response': 'images',
        'include_image_language': 'en,null'
    }
    r = movie.movie(movie_id, params=params)
    print(json.dumps(r))


if __name__ == '__main__':
    search_movie('The.Others.2001.1080p.BluRay.x265-RARBG')
