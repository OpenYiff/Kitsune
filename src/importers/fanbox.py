import sys
sys.path.append('./PixivUtil2')
sys.setrecursionlimit(100000)

from os import makedirs
from os.path import join
import requests
import datetime
import config
import json
import logging
import uuid

from ...PixivUtil2.PixivModelFanbox import FanboxArtist, FanboxPost

from ..internals.database.database import get_conn, return_conn
from ..lib.artist import delete_artist_cache_keys, delete_all_artist_keys, index_artists
from ..lib.post import delete_post_cache_keys, delete_all_post_cache_keys, remove_post_if_flagged_for_reimport
from ..lib.proxy import get_proxy
from ..lib.download import download_file, DownloaderException

def import_posts(log_id, key, url = 'https://api.fanbox.cc/post.listSupporting?limit=50'):
    makedirs(join(config.download_path, 'logs'), exist_ok=True)
    sys.stdout = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')
    # sys.stderr = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')

    conn = get_conn()

    try:
        scraper = requests.get(
            url,
            cookies={ 'FANBOXSESSID': key },
            headers={ 'origin': 'https://fanbox.cc' },
            proxies=get_proxy()
        )
        scraper_data = scraper.json()
    except requests.HTTPError:
        print(f'Error: Status code {scraper.status_code} when contacting Patreon API.')
        return

    user_id = None

    if scraper_data.get('body'):
        for post in scraper_data['body']['items']:
            user_id = post['user']['userId']
            post_id = post['id']

            parsed_post = FanboxPost(post_id, None, post)
            if parsed_post.is_restricted:
                continue
            try:
                file_directory = f"files/fanbox/{user_id}/{post_id}"
                attachments_directory = f"attachments/fanbox/{user_id}/{post_id}"

                cursor1 = conn.cursor()
                cursor1.execute("SELECT * FROM dnp WHERE id = %s AND service = 'fanbox'", (user_id,))
                bans = cursor1.fetchall()
                if len(bans) > 0:
                    print(f"Skipping ID {post_id}: user {user_id} is banned")
                    continue
                
                remove_post_if_flagged_for_reimport('fanbox', user_id, post_id)

                cursor2 = conn.cursor()
                cursor2.execute("SELECT * FROM posts WHERE id = %s AND service = 'fanbox'", (post_id,))
                existing_posts = cursor2.fetchall()
                if len(existing_posts) > 0:
                    continue

                print(f"Starting import: {post_id}")

                post_model = {
                    'id': post_id,
                    '"user"': user_id,
                    'service': 'fanbox',
                    'title': post['title'],
                    'content': parsed_post.body_text,
                    'embed': {},
                    'shared_file': False,
                    'added': datetime.datetime.now(),
                    'published': post['publishedDatetime'],
                    'edited': post['updatedDatetime'],
                    'file': {},
                    'attachments': []
                }

                for i in range(len(parsed_post.embeddedFiles)):
                    if i == 0:
                        filename, _ = download_file(
                            join(config.download_path, file_directory),
                            parsed_post.embeddedFiles[i],
                            cookies={ 'FANBOXSESSID': key },
                            headers={ 'origin': 'https://fanbox.cc' }
                        )
                        post_model['file']['name'] = filename
                        post_model['file']['path'] = f'/{file_directory}/{filename}'
                    else:
                        filename, _ = download_file(
                            join(config.download_path, attachments_directory),
                            parsed_post.embeddedFiles[i],
                            cookies={ 'FANBOXSESSID': key },
                            headers={ 'origin': 'https://fanbox.cc' }
                        )
                        post_model['attachments'].append({
                            'name': filename,
                            'path': f'/{attachments_directory}/{filename}'
                        })

                post_model['embed'] = json.dumps(post_model['embed'])
                post_model['file'] = json.dumps(post_model['file'])
                for i in range(len(post_model['attachments'])):
                    post_model['attachments'][i] = json.dumps(post_model['attachments'][i])

                columns = post_model.keys()
                data = ['%s'] * len(post_model.values())
                data[-1] = '%s::jsonb[]' # attachments
<<<<<<< HEAD
                query = "INSERT INTO posts ({fields}) VALUES ({values})".format(
=======
                query = "INSERT INTO booru_posts ({fields}) VALUES ({values})".format(
>>>>>>> Revert "Separate booru_posts into separate tables"
                    fields = ','.join(columns),
                    values = ','.join(data)
                )
                cursor3 = conn.cursor()
                cursor3.execute(query, list(post_model.values()))
                conn.commit()

                post.delete_post_cache_keys('fanbox', user_id, post_id)

                print(f"Finished importing {post_id}!")
            except Exception as e:
                print(f"Error while importing {post_id}: {e}")
                conn.rollback()
                continue
        
        if scraper_data['body'].get('nextUrl'):
            import_posts(log_id, key, scraper_data['body']['nextUrl'])
        else:
            print('Finished scanning for posts.')
            index_artists()

            if user_id is not None:
                artist.delete_artist_cache_keys('fanbox', user_id)
            artist.delete_all_artist_keys()
            post.delete_all_post_cache_keys()
    
    return_conn(conn)
    
if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_posts(str(uuid.uuid4()), sys.argv[1])
    else:
        print('Argument required - Login token')
