from flask import Flask, request, redirect
from indexer import index_artists
from bs4 import BeautifulSoup
from yoyo import read_migrations
from yoyo import get_backend
from download import download_file
from os.path import join, exists
from proxy import get_proxy
from os import makedirs
import cloudscraper
import requests
import threading
import uuid
import re
import logging
import uwsgi

import src.internals.database.database
import src.internals.cache.redis
import src.importers.patreon
import src.importers.fanbox
import src.importers.subscribestar
import src.importers.gumroad

from src.endpoints.api import api
from src.endpoints.icons import icons
from src.endpoints.banners import banners

app = Flask(__name__)

app.register_blueprint(api)
app.register_blueprint(icons)
app.register_blueprint(banners)

logging.basicConfig(filename='kemono.log', level=logging.DEBUG)

if uwsgi.worker_id() == 0:
    backend = get_backend(f'postgres://{config.database_user}:{config.database_password}@{config.database_host}/{config.database_dbname}')
    migrations = read_migrations('./migrations')
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
    index_artists()

database.init()
redis.init()

@app.teardown_appcontext
def close(e):
    cursor = g.pop('cursor', None)
    if cursor is not None:
        cursor.close()
        connection = g.pop('connection', None)
        if connection is not None:
            connection.commit()
            pool = database.get_pool()
            pool.putconn(connection)
