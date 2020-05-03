# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class DriveItem(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    createdDateTime = db.Column(db.DateTime)
    lastModifiedDateTime = db.Column(db.DateTime)
    size = db.Column(db.Integer, nullable=False)
    drive_id = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.String(50), nullable=False)
    parent_path = db.Column(db.String(1000), nullable=False)
    type = db.Column(db.Enum('file', 'folder'), nullable=False)
    childCount = db.Column(db.Integer, default=0)


class Movie(db.Model):
    id = db.Column(db.String(200), primary_key=True)
