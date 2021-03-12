import cloudscraper
import psycopg2
import datetime
import config
import time
import uuid
import json
import sys
import logging
import requests

sys.setrecursionlimit(100000)

from indexer import index_artists
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from os import makedirs
from os.path import join, splitext
from download import download_file, DownloaderException
from gallery_dl import text
from flag_check import check_for_flags
from proxy import get_proxy

from ..internals.database.database import get_conn

initial_api = 'https://www.patreon.com/api/stream' + '?include=' + ','.join([
    'user',
    'images',
    'audio',
    'attachments',
    'user_defined_tags',
    'campaign',
    'poll.choices',
    'poll.current_user_responses.user',
    'poll.current_user_responses.choice',
    'poll.current_user_responses.poll',
    'access_rules.tier.null'
]) + '&fields[post]=' + ','.join([
    'change_visibility_at',
    'comment_count',
    'content',
    'current_user_can_delete',
    'current_user_can_view',
    'current_user_has_liked',
    'embed',
    'image',
    'is_paid',
    'like_count',
    'min_cents_pledged_to_view',
    'post_file',
    'published_at',
    'edited_at',
    'patron_count',
    'patreon_url',
    'post_type',
    'pledge_url',
    'thumbnail_url',
    'teaser_text',
    'title',
    'upgrade_url',
    'url',
    'was_posted_by_campaign_owner',
]) + '&fields[user]=' + ','.join([
    'image_url',
    'full_name',
    'url'
]) + '&fields[campaign]=' + ','.join([
    'avatar_photo_url',
    'earnings_visibility',
    'is_nsfw',
    'is_monthly',
    'name',
    'url'
]) + '&json-api-use-default-includes=false' + '&json-api-version=1.0'

def import_posts(log_id, key, url = initial_api):
    makedirs(join(config.download_path, 'logs'), exist_ok=True)
    sys.stdout = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')
    # sys.stderr = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')

    conn = get_conn()

    try:
        scraper = cloudscraper.create_scraper().get(url, cookies = { 'session_id': key }, proxies=get_proxy())
        scraper_data = scraper.json()
        scraper.raise_for_status()
    except requests.HTTPError:
        print(f'Error: Status code {scraper_data.status_code} when contacting Patreon API.')
        return
    
    for post in scraper_data['data']:
        try:
            file_directory = f"files/{post['relationships']['user']['data']['id']}/{post['id']}"
            attachments_directory = f"attachments/{post['relationships']['user']['data']['id']}/{post['id']}"

            cursor1 = conn.cursor()
            cursor1.execute("SELECT * FROM dnp WHERE id = %s AND service = 'patreon'", (post['relationships']['user']['data']['id'],))
            bans = cursor1.fetchall()
            if len(bans) > 0:
                print(f"Skipping ID {post['id']}: user {post['relationships']['user']['data']['id']} is banned")
                return
            
            check_for_flags(
                'patreon',
                post['relationships']['user']['data']['id'],
                post['id']
            )

            cursor2 = conn.cursor()
            cursor2.execute("SELECT * FROM posts WHERE id = %s AND service = 'patreon'", (post['id'],))
            existing_post = cursor2.fetchall()
            if len(existing_post) > 0:
                continue

            print(f"Starting import: {post['id']}")

            post_model = {
                'id': post['id'],
                '"user"': post['relationships']['user']['data']['id'],
                'service': 'patreon',
                'title': post['attributes']['title'] or "",
                'content': '',
                'embed': {},
                'shared_file': False,
                'added': datetime.datetime.now(),
                'published': post['attributes']['published_at'],
                'edited': post['attributes']['edited_at'],
                'file': {},
                'attachments': []
            }

            if post['attributes']['content']:
                post_model['content'] = post['attributes']['content']
                for image in text.extract_iter(post['attributes']['content'], '<img data-media-id="', '>'):
                    download_url = text.extract(image, 'src="', '"')[0]
                    path = urlparse(download_url).path
                    ext = splitext(path)[1]
                    fn = str(uuid.uuid4()) + ext
                    filename, _ = download_file(
                        join(config.download_path, 'inline'),
                        download_url,
                        name = fn
                    )
                    post_model['content'] = post_model['content'].replace(download_url, f"/inline/{filename}")

            if post['attributes']['embed']:
                post_model['embed']['subject'] = post['attributes']['embed']['subject']
                post_model['embed']['description'] = post['attributes']['embed']['description']
                post_model['embed']['url'] = post['attributes']['embed']['url']

            if post['attributes']['post_file']:
                filename, _ = download_file(
                    join(config.download_path, file_directory),
                    post['attributes']['post_file']['url'],
                    name = post['attributes']['post_file']['name']
                )
                post_model['file']['name'] = post['attributes']['post_file']['name']
                post_model['file']['path'] = f'/{file_directory}/{filename}'

            for attachment in post['relationships']['attachments']['data']:
                filename, _ = download_file(
                    join(config.download_path, attachments_directory),
                    f"https://www.patreon.com/file?h={post['id']}&i={attachment['id']}",
                    cookies = { 'session_id': key }
                )
                post_model['attachments'].append({
                    'name': filename,
                    'path': f'/{attachments_directory}/{filename}'
                })

            if post['relationships']['images']['data']:
                for image in post['relationships']['images']['data']:
                    for media in list(filter(lambda included: included['id'] == image['id'], scraper_data['included'])):
                        if media['attributes']['state'] != 'ready':
                            continue
                        filename, _ = download_file(
                            join(config.download_path, attachments_directory),
                            media['attributes']['download_url'],
                            name = media['attributes']['file_name']
                        )
                        post_model['attachments'].append({
                            'name': filename,
                            'path': f'/{attachments_directory}/{filename}'
                        })

            if post['relationships']['audio']['data']:
                for media in list(filter(lambda included: included['id'] == post['relationships']['audio']['data']['id'], scraper_data['included'])):
                    if media['attributes']['state'] != 'ready':
                        continue
                    filename, _ = download_file(
                        join(config.download_path, attachments_directory),
                        media['attributes']['download_url'],
                        name = media['attributes']['file_name']
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

    conn.close()
    if scraper_data['links'].get('next'):
        import_posts(log_id, key, 'https://' + scraper_data['links']['next'])
    else:
        print('Finished scanning for posts.')
        print('No posts detected? You either entered your session key incorrectly, or are not subscribed to any artists.')
        index_artists()

    

if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_posts(str(uuid.uuid4()), sys.argv[1])
    else:
        print('Argument required - Login token')