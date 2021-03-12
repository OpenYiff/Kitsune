from ..internals.cache.redis import delete_keys, delete_wildcard_keys

def delete_post_cache_keys(service, artist_id, post_id):
    keys = []
    wildcard_keys = [
        'post:' + service + ':' + str(artist_id) + ':' + post_id
    ]

    delete_wildcard_keys(wildcard_keys)

def delete_all_post_cache_keys():
    keys = ['all_post_keys']

    delete_keys(keys)
