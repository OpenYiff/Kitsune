from ..internals.cache.redis import delete_keys
from ..internals.database.database import get_cursor, get_conn, return_conn
from shutil import rmtree
from os.path import join
import config

def delete_post_cache_keys(service, artist_id, post_id):
    keys = [
        'post:' + service + ':' + str(artist_id) + ':' + str(post_id)
    ]

    delete_keys(keys)

def delete_all_post_cache_keys():
    keys = ['all_post_keys']

    delete_keys(keys)

def post_exists(service, artist_id, post_id):
    cursor = get_cursor()
    cursor.execute("SELECT * FROM posts WHERE id = %s AND \"user\" = %s AND service = %s", (post_id, artist_id, service,))
    return len(cursor.fetchall()) > 0

def remove_post_if_flagged_for_reimport(service, user, post):
    conn = get_conn()
    cursor = get_cursor()

    cursor.execute('SELECT * FROM booru_flags WHERE service = %s AND "user" = %s AND id = %s', (service, user, post))
    existing_flags = cursor.fetchall()
    if len(existing_flags) == 0:
        return

    cursor.execute('DELETE FROM booru_flags WHERE service = %s AND "user" = %s AND id = %s', (service, user, post))
    cursor.execute('DELETE FROM posts WHERE service = %s AND "user" = %s AND id = %s', (service, user, post))
    conn.commit()
    return_conn(conn)
    rmtree(join(
        config.download_path,
        'attachments',
        '' if service == 'patreon' else service,
        user,
        post
    ), ignore_errors=True)
    rmtree(join(
        config.download_path,
        'files',
        '' if service == 'patreon' else service,
        user,
        post
    ), ignore_errors=True)
