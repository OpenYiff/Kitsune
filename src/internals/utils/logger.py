from flask import current_app, session

from threading import Lock
from .utils import get_value
from ..cache.redis import get_redis

log_lock = Lock()

def log(log_id, msg, level = 'debug', to_client = True):
    redis = get_redis()
    log_lock.acquire()
    try:
        msg = f'[{log_id}]: {msg}'
        log_func = getattr(current_app.logger, level)
        log_func(msg)

        if to_client:
            redis.rpush(f'importer_logs:{log_id}', msg)
    finally:
        log_lock.release()

def get_logs(log_id):
    redis = get_redis()
    log_lock.acquire()
    try:
        key = f'importer_logs:{log_id}'
        llen = redis.llen(key)

        messages = []
        if llen > 0:
            messages = redis.lrange(key, 0, llen)
    finally:
        log_lock.release()

    return list(map(lambda msg: msg.decode('utf-8'), messages))
