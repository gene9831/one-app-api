# -*- coding: utf-8 -*-

from flask import Blueprint
from flask_jsonrpc import JSONRPCBlueprint

from app.common import AuthorizationSite

onedrive_bp = JSONRPCBlueprint('onedrive', __name__)
onedrive_admin_bp = JSONRPCBlueprint('onedrive_admin', __name__,
                                     jsonrpc_site=AuthorizationSite)
onedrive_route_bp = Blueprint('onedrive_route', __name__)


def init():
    from . import sign_in, item, upload, manage


init()
