# -*- coding: utf-8 -*-
from typing import Literal, Optional

from flask_jsonrpc.exceptions import InvalidRequestError

from app import jsonrpc_bp
from .. import mongodb

get_movie_projection = {
    '_id': 0,
    'id': 1,
    'genres': 1,
    'belongs_to_collection': 1,
    'images.backdrops': {'$slice': ["$images.backdrops", 3]},
    "images.posters": {'$slice': ["$images.posters", 3]},
    'original_language': 1,
    'original_title': 1,
    'overview': 1,
    'release_date': 1,
    'runtime': 1,
    'status': 1,
    'title': 1,
    'directors': 1,
}


@jsonrpc_bp.method('TMDb.getMovie')
def get_movie(movie_id: int, append_collection: bool = False) -> dict:
    for item in mongodb.tmdb_movie.aggregate([
        {'$match': {'id': movie_id}},
        {'$lookup': {
            'from': 'tmdb_person',
            'localField': 'directors',
            'foreignField': 'id',
            'as': 'directors'
        }},
        {'$unset': 'directors._id'},
        {'$project': get_movie_projection}
    ]):
        if append_collection and item.get('belongs_to_collection') is not None:
            item['belongs_to_collection'] = get_collection(
                item['belongs_to_collection']['id'])
        return item

    raise InvalidRequestError(message='Invalid movie id')


get_movies_projection = get_movie_projection.copy()
get_movies_projection.pop('overview', None)
get_movies_projection.pop('runtime', None)
get_movies_projection.pop('images.backdrops', None)
get_movies_projection.pop('images.posters', None)
get_movies_projection.pop('belongs_to_collection', None)
get_movies_projection.pop('directors', None)


@jsonrpc_bp.method('TMDb.getMovies')
def get_movies(
        match: dict = None,
        skip: int = 0, limit: int = 25,
        order: Literal['asc', 'desc'] = 'desc',
        order_by: Literal['release_date'] = 'release_date'
) -> dict:
    if match is None:
        match = {}
    for result in mongodb.tmdb_movie.aggregate([
        {'$lookup': {
            'from': 'tmdb_person',
            'localField': 'directors',
            'foreignField': 'id',
            'as': 'directors'
        }},
        {'$match': match},
        {'$set': {'poster': {'$arrayElemAt': ['$images.posters', 0]}}},
        {'$project': {
            **get_movies_projection,
            'poster_path': '$poster.file_path'
        }},
        {'$facet': {
            'count': [{'$count': 'count'}],
            'list': [
                {'$sort': {
                    order_by: 1 if order == 'asc' else -1,
                    # 多个电影release_date相同，导致sort排序不稳定，再加个title字段
                    'title': 1
                }},
                {'$skip': skip},
                {'$limit': limit}
            ]
        }},
        {'$set': {'count': {'$let': {
            'vars': {'firstElem': {'$arrayElemAt': ['$count', 0]}},
            'in': '$$firstElem.count'
        }}}},
        {'$set': {'count': {'$ifNull': ['$count', {'$toInt': 0}]}}}
    ]):
        return result

    return {'count': 0, 'list': []}


@jsonrpc_bp.method('TMDb.getCollection')
def get_collection(collection_id: int) -> Optional[dict]:
    for item in mongodb.tmdb_collection.aggregate([
        {'$match': {'id': collection_id}},
        {'$unset': 'parts.overview'},
        {'$unwind': '$parts'},
        {'$lookup': {
            'from': 'tmdb_movie',
            'localField': 'parts.id',
            'foreignField': 'id',
            'as': 'movies'
        }},
        {'$addFields': {'parts.included': {'$cond': [
            {'$eq': [{'$size': '$movies'}, 0]}, False, True]
        }}},
        {'$group': {
            '_id': '$id',
            'id': {'$first': '$id'},
            'backdrop_path': {'$first': '$backdrop_path'},
            'name': {'$first': '$name'},
            'overview': {'$first': '$overview'},
            'parts': {'$push': '$parts'},
            'poster_path': {'$first': '$poster_path'},
        }},
        {'$unset': '_id'}
    ]):
        return item

    return None


@jsonrpc_bp.method('TMDb.getMovieGenres')
def get_movie_genres() -> list:
    res = []

    for item in mongodb.tmdb_genre.find({}, {'_id': 0}):
        res.append(item)

    return res


item_projection = {
    '_id': 0, 'id': 1, 'name': 1, 'file': 1, 'folder': 1,
    'lastModifiedDateTime': 1, 'size': 1
}


@jsonrpc_bp.method('TMDb.getItemsByMovieId')
def get_items_by_movie_id(movie_id: int) -> list:
    res = []
    for item in mongodb.item.find({'movie_id': movie_id}, item_projection):
        if 'file' in item.keys():
            res.append(item)
        elif 'folder' in item.keys():
            for itm in mongodb.item.find({'parentReference.id': item['id']},
                                         item_projection):
                res.append(itm)
    if len(res) == 0:
        # 没有资源
        mongodb.tmdb_movie.delete_one({'id': movie_id})

    return res
