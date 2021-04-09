from datetime import datetime
from flask import request
import hashlib
import random

def get_value(d, key, default = None):
    if key in d:
        return d[key]
    return default

def sort_dict_list_by(l, key, reverse = False):
    return sorted(l, key=lambda v: v[key], reverse=reverse)

def restrict_value(value, allowed, default = None):
    if value not in allowed:
        return default
    return value

def take(num, l):
    if len(l) <= num:
        return l
    return l[:num]

def offset(num, l):
    if len(l) <= num:
        return []
    return l[num:]

def limit_int(i, limit):
    if i > limit:
        return limit
    return i

def parse_int(string, default = 0):
    try:
        return int(string)
    except Exception:
        return default

def get_import_id(data):
    salt = str(random.randrange(0, 1000))
    return take(7, hashlib.sha256((data + salt).encode('utf-8')).hexdigest())
