import sys
sys.path.append('./PixivUtil2')
sys.setrecursionlimit(100000)

import psycopg2
import requests
import datetime
import config
import json
import logging
import uuid

from indexer import index_artists
from psycopg2.extras import RealDictCursor
from PixivUtil2.PixivModelFanbox import FanboxArtist, FanboxPost
from proxy import get_proxy
from download import download_file, DownloaderException
from flag_check import check_for_flags
from os import makedirs
from os.path import join
def import_posts(log_id, key, url = 'https://api.fanbox.cc/post.listSupporting?limit=50'):
    makedirs(join(config.download_path, 'logs'), exist_ok=True)
    sys.stdout = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')
    # sys.stderr = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')

    conn = psycopg2.connect(
        host = config.database_host,
        dbname = config.database_dbname,
        user = config.database_user,
        password = config.database_password,
        cursor_factory = RealDictCursor
    )

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

    if scraper_data.get('body'):
        for post in scraper_data['body']['items']:
            parsed_post = FanboxPost(post['id'], None, post)
            if parsed_post.is_restricted:
                continue
            try:
                file_directory = f"files/fanbox/{post['user']['userId']}/{post['id']}"
                attachments_directory = f"attachments/fanbox/{post['user']['userId']}/{post['id']}"

                cursor1 = conn.cursor()
                cursor1.execute("SELECT * FROM dnp WHERE id = %s AND service = 'fanbox'", (post['user']['userId'],))
                bans = cursor1.fetchall()
                if len(bans) > 0:
                    print(f"Skipping ID {post['id']}: user {post['user']['userId']} is banned")
                    continue
                
                check_for_flags(
                    'fanbox',
                    post['user']['userId'],
                    post['id']
                )

                cursor2 = conn.cursor()
                cursor2.execute("SELECT * FROM posts WHERE id = %s AND service = 'fanbox'", (post['id'],))
                existing_posts = cursor2.fetchall()
                if len(existing_posts) > 0:
                    continue

                print(f"Starting import: {post['id']}")

                post_model = {
                    'id': post['id'],
                    '"user"': post['user']['userId'],
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
                print(f"Finished importing {post['id']}!")
            except Exception as e:
                print(f"Error while importing {post['id']}: {e}")
                conn.rollback()
                continue
        
        if scraper_data['body'].get('nextUrl'):
            import_posts(log_id, key, scraper_data['body']['nextUrl'])
        else:
            print('Finished scanning for posts.')
            index_artists()
    
    conn.close()
    
if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_posts(str(uuid.uuid4()), sys.argv[1])
    else:
        print('Argument required - Login token')