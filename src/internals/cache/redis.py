import redis
from os import getenv

pool = None

def init():
    global pool
    pool = redis.ConnectionPool(host=getenv('REDIS_HOST'), port=getenv('REDIS_PORT'))
    return pool

def get_redis():
    return redis.Redis(connection_pool=pool)

def delete_keys(keys):
    conn = get_redis()
    for key in keys:
        conn.delete(key)

def delete_keys_pattern(pattern):
    redis = get_conn()
    keys = redis.keys(pattern)
    redis.delete(*keys)

