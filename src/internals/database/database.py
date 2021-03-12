import psycopg2
from psycopg2.extras import RealDictCursor
from os import getenv

pool = None

def init():
    global pool
    try:
        pool = psycopg2.pool.ThreadedConnectionPool(1, 100,
            host = getenv('PGHOST'),
            dbname = getenv('PGDATABASE'),
            user = getenv('PGUSER'),
            password = getenv('PGPASSWORD'),
            port = getenv('PGPORT') or 5432,
            cursor_factory = RealDictCursor
        )
    except Exception as error:
        print("Failed to connect to the database: ", error)
    return pool

def get_pool():
    return pool

def get_conn():
    return pool.getconn()

def return_conn(conn):
    pool.putconn(conn)
