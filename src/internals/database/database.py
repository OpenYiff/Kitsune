from flask import g, current_app
import psycopg2
from psycopg2.extras import RealDictCursor
from os import getenv

pool = None

def init():
    global pool
    try:
        pool = psycopg2.pool.ThreadedConnectionPool(1, 2000,
            host = getenv('PGHOST'),
            dbname = getenv('PGDATABASE'),
            user = getenv('PGUSER'),
            password = getenv('PGPASSWORD'),
            port = getenv('PGPORT') or 5432,
            cursor_factory = RealDictCursor
        )
    except Exception as error:
        current_app.logger.error(f'Failed to connect to the database: {error}')
    return pool

def get_pool():
    global pool
    return pool

def get_cursor():
    if 'cursor' not in g:
        g.connection = get_conn()
        g.cursor = g.connection.cursor()
    return g.cursor

def get_conn():
    if 'connection' not in g:
        g.connection = pool.getconn()
    return g.connection
