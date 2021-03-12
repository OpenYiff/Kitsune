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

def delete_wildcard_keys(wildcards):
    conn = get_redis()
    for wildcard in wildcards:
        keys = conn.keys(pattern=wildcard)
        delete_keys(keys)
