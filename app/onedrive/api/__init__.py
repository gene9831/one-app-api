# -*- coding: utf-8 -*-

from flask import Blueprint

onedrive_route_bp = Blueprint('onedrive_route', __name__)
onedrive_root_path = '/drive/root:'


def init():
    from . import sign_in, item, upload, manage


init()
