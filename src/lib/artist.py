from ..internals.cache.redis import delete_keys, delete_wildcard_keys

def delete_artist_cache_keys(service, artist_id):
    artist_id = str(artist_id)
    keys = [
        'artists_by_service:' + service,
        'artist:' + service + ':' + artist_id,
        'artist_post_count:' + service + ':' + artist_id,
        'posts_by_artist:' + service + ':' + artist_id,
    ]
    wildcard_keys = [
        'artist_posts_offset:' + service + ':' + artist_id + ':*',
        'is_post_flagged:' + service + ':' + artist_id + ':*',
        'next_post:' + service + ':' + artist_id + ':*',
        'previous_post:' + service + ':' + artist_id + ':*'
    ]

    delete_keys(keys)
    delete_wildcard_keys(wildcard_keys)

def delete_all_artist_keys():
    keys = [
        'non_discord_artist_keys',
        'non_discord_artists'
    ]
    
    delete_keys(keys)
