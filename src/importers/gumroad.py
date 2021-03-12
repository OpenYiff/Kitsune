import sys
sys.setrecursionlimit(100000)

import re
import config
import requests
import cloudscraper
import uuid
import json
import datetime
from bs4 import BeautifulSoup
from os.path import join
from os import makedirs

from ..internals.database.database import get_conn, return_conn
from ..lib.artist import delete_artist_cache_keys, delete_all_artist_keys, index_artists
from ..lib.post import delete_post_cache_keys, delete_all_post_cache_keys, remove_post_if_flagged_for_reimport
from ..lib.download import download_file, DownloaderException
from ..lib.proxy import get_proxy

def import_posts(log_id, key, startFrom = 1):
    makedirs(join(config.download_path, 'logs'), exist_ok=True)
    sys.stdout = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')
    # sys.stderr = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')

    conn = get_conn()

    try:
        scraper = cloudscraper.create_scraper().get(
            f"https://gumroad.com/discover_search?from={startFrom}&user_purchases_only=true",
            cookies = { '_gumroad_app_session': key },
            proxies=get_proxy()
        )
        scraper_data = scraper.json()
        scraper.raise_for_status()
    except requests.HTTPError:
        print(f'Error: Status code {scraper_data.status_code} when contacting Gumroad API.')
        return

    if (scraper_data['total'] > 100000):
        print(f'Error: Can\'t log in; is your session key correct?')

    soup = BeautifulSoup(scraper_data['products_html'], 'html.parser')
    products = soup.find_all(class_='product-card')
	
    user_id = None

    for product in products:
        post_id = product['data-permalink']
        purchase_id = product.find(class_='js-product')['data-purchase-id']
        title = product.select_one('.description-container h1 strong').string
        user_id_element = product.find(class_='preview-container')['data-asset-previews']
        user_id_nums = re.findall(r"\d+", user_id_element)
        user_id = list(filter(lambda el: len(el) == 13, user_id_nums))[0]

        file_directory = f"files/gumroad/{user_id}/{post_id}"
        attachments_directory = f"attachments/gumroad/{user_id}/{post_id}"

        cursor1 = conn.cursor()
        cursor1.execute("SELECT * FROM dnp WHERE id = %s AND service = 'gumroad'", (user_id,))
        bans = cursor1.fetchall()
        if len(bans) > 0:
            print(f"Skipping ID {post_id}: user {user_id} is banned")
            continue
        
        check_for_flags(
            'gumroad',
            user_id,
            post_id
        )

        cursor2 = conn.cursor()
        cursor2.execute("SELECT * FROM posts WHERE id = %s AND service = 'gumroad'", (post_id,))
        existing_posts = cursor2.fetchall()
        if len(existing_posts) > 0:
            continue

        print(f"Starting import: {post_id}")

        post_model = {
            'id': post_id,
            '"user"': user_id,
            'service': 'gumroad',
            'title': title,
            'content': '',
            'embed': {},
            'shared_file': False,
            'added': datetime.datetime.now(),
            'published': None,
            'edited': None,
            'file': {},
            'attachments': []
        }
        
        scraper2 = cloudscraper.create_scraper().get(
            f"https://gumroad.com/library/purchases/{purchase_id}",
            cookies = { '_gumroad_app_session': key },
            proxies=get_proxy()
        )
        scraper_data2 = scraper2.text
        soup2 = BeautifulSoup(scraper_data2, 'html.parser')
        content_url = soup2.select_one('.button.button-primary.button-block')['href']

        scraper3 = cloudscraper.create_scraper().get(
            content_url,
            cookies = { '_gumroad_app_session': key },
            proxies=get_proxy()
        )
        scraper_data3 = scraper3.text
        soup3 = BeautifulSoup(scraper_data3, 'html.parser')
        thumbnail1 = soup3.select_one('.image-preview-container img').get('src') if soup3.select_one('.image-preview-container img') else None
        thumbnail2 = soup3.select_one('.image-preview-container img').get('data-cfsrc') if soup3.select_one('.image-preview-container img') else None
        thumbnail3 = soup3.select_one('.image-preview-container noscript img').get('src') if soup3.select_one('.image-preview-container noscript img') else None
        try:
            download_data = json.loads(soup3.select_one('div[data-react-class="DownloadPage/FileList"]')['data-react-props'])
        except:
            download_data = {
              "files": [],
              "download_info": {}
            }
        
        thumbnail = thumbnail1 or thumbnail2 or thumbnail3
        if thumbnail:
            filename, _ = download_file(
                join(config.download_path, file_directory),
                thumbnail
            )
            post_model['file']['name'] = filename
            post_model['file']['path'] = f'/{file_directory}/{filename}'
        
        for _file in download_data['files']:
            filename, _ = download_file(
                join(config.download_path, attachments_directory),
                'https://gumroad.com' + download_data['download_info'][_file['id']]['download_url'],
                name = f'{_file["file_name"]}.{_file["extension"].lower()}',
                cookies = { '_gumroad_app_session': key }
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
        query = "INSERT INTO posts ({fields}) VALUES ({values})".format(
            fields = ','.join(columns),
            values = ','.join(data)
        )
        cursor3 = conn.cursor()
        cursor3.execute(query, list(post_model.values()))
        conn.commit()

        post.delete_post_cache_keys('gumroad', user_id, post_id)

        print(f"Finished importing {post_id}!")

    if len(products):
        import_posts(log_id, key, startFrom=startFrom + scraper_data['result_count'])
    else:
        print('Finished scanning for posts.')
        index_artists()

        if user_id is not None:
                artist.delete_artist_cache_keys('gumroad', user_id)
        artist.delete_all_artist_keys()
        post.delete_all_post_cache_keys()
    
    return_conn(conn)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_posts(str(uuid.uuid4()), sys.argv[1])
    else:
        print('Argument required - Login token')
