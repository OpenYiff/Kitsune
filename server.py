from flask import Flask, request, redirect
from indexer import index_artists
import patreon_importer
import fanbox_importer
import subscribestar_importer
import gumroad_importer
from bs4 import BeautifulSoup
from yoyo import read_migrations
from yoyo import get_backend
from download import download_file
from os.path import join, exists
from proxy import get_proxy
from os import makedirs
import cloudscraper
import requests
import threading
import uuid
import re
import logging
import uwsgi

app = Flask(__name__)

logging.basicConfig(filename='kemono.log', level=logging.DEBUG)

if uwsgi.worker_id() == 0:
    backend = get_backend(f'postgres://{config.database_user}:{config.database_password}@{config.database_host}/{config.database_dbname}')
    migrations = read_migrations('./migrations')
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
    index_artists()

class FanboxIconException(Exception):
    pass

@app.route('/api/import', methods=['POST'])
def import_api():
    log_id = str(uuid.uuid4())
    if not request.args.get('session_key'):
        return "", 401
    if request.args.get('service') == 'patreon':
        th = threading.Thread(target=patreon_importer.import_posts, args=(log_id, request.args.get('session_key')))
        th.start()
    elif request.args.get('service') == 'fanbox':
        th = threading.Thread(target=fanbox_importer.import_posts, args=(log_id, request.args.get('session_key')))
        th.start()
    elif request.args.get('service') == 'subscribestar':
        th = threading.Thread(target=subscribestar_importer.import_posts, args=(log_id, request.args.get('session_key')))
        th.start()
    elif request.args.get('service') == 'gumroad':
        th = threading.Thread(target=gumroad_importer.import_posts, args=(log_id, request.args.get('session_key')))
        th.start()
    return log_id, 200

@app.route('/icons/<service>/<user>')
def import_icon(service, user):
    makedirs(join(config.download_path, 'icons', service), exist_ok=True)
    if not exists(join(config.download_path, 'icons', service, user)):
        try:
            if service == 'patreon':
                scraper = cloudscraper.create_scraper().get('https://www.patreon.com/api/user/' + user, proxies=get_proxy())
                data = scraper.json()
                scraper.raise_for_status()
                download_file(
                    join(config.download_path, 'icons', service),
                    data['included'][0]['attributes']['avatar_photo_url'] if data.get('included') else data['data']['attributes']['image_url'],
                    name = user
                )
            elif service == 'fanbox':
                scraper = requests.get('https://api.fanbox.cc/creator.get?userId=' + user, headers={"origin":"https://fanbox.cc"}, proxies=get_proxy())
                data = scraper.json()
                scraper.raise_for_status()
                if data['body']['user']['iconUrl']:
                    download_file(
                        join(config.download_path, 'icons', service),
                        data['body']['user']['iconUrl'],
                        name = user
                    )
                else:
                    raise FanboxIconException()
            elif service == 'subscribestar':
                scraper = requests.get('https://subscribestar.adult/' + user, proxies=get_proxy())
                data = scraper.text
                scraper.raise_for_status()
                soup = BeautifulSoup(data, 'html.parser')
                download_file(
                    join(config.download_path, 'icons', service),
                    soup.find('div', class_='profile_main_info-userpic').contents[0]['src'],
                    name = user
                )
            elif service == 'gumroad':
                scraper = requests.get('https://gumroad.com/' + user, proxies=get_proxy())
                data = scraper.text
                scraper.raise_for_status()
                soup = BeautifulSoup(data, 'html.parser')
                download_file(
                    join(config.download_path, 'icons', service),
                    re.findall(r'(?:http\:|https\:)?\/\/.*\.(?:png|jpe?g|gif)', soup.find('div', class_='profile-picture js-profile-picture')['style'], re.IGNORECASE)[0],
                    name = user
                )
            else:
                with open(join(config.download_path, 'icons', service, user), 'w') as _: 
                    pass
        except FanboxIconException:
            with open(join(config.download_path, 'icons', service, user), 'w') as _: 
                pass
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                with open(join(config.download_path, 'icons', service, user), 'w') as _: 
                    pass
    
    response = redirect(join('/', 'icons', service, user), code=302)
    response.autocorrect_location_header = False
    return response

@app.route('/banners/<service>/<user>')
def import_banner(service, user):
    makedirs(join(config.download_path, 'banners', service), exist_ok=True)
    if not exists(join(config.download_path, 'banners', service, user)):
        try:
            if service == 'patreon':
                scraper = cloudscraper.create_scraper().get('https://www.patreon.com/api/user/' + user, proxies=get_proxy())
                data = scraper.json()
                scraper.raise_for_status()
                if data.get('included') and data['included'][0]['attributes'].get('cover_photo_url'):
                    download_file(
                        join(config.download_path, 'banners', service),
                        data['included'][0]['attributes']['cover_photo_url'],
                        name = user
                    )
                else:
                    raise FanboxIconException()
            elif service == 'fanbox':
                scraper = requests.get('https://api.fanbox.cc/creator.get?userId=' + user, headers={"origin":"https://fanbox.cc"}, proxies=get_proxy())
                data = scraper.json()
                scraper.raise_for_status()
                if data['body']['coverImageUrl']:
                    download_file(
                        join(config.download_path, 'banners', service),
                        data['body']['coverImageUrl'],
                        name = user
                    )
                else:
                    raise FanboxIconException()
            elif service == 'subscribestar':
                scraper = requests.get('https://subscribestar.adult/' + user, proxies=get_proxy())
                data = scraper.text
                scraper.raise_for_status()
                soup = BeautifulSoup(data, 'html.parser')
                if soup.find('div', class_='profile_main_info-cover'):
                    download_file(
                        join(config.download_path, 'banners', service),
                        soup.find('div', class_='profile_main_info-cover').contents[0]['src'],
                        name = user
                    )
                else:
                    raise FanboxIconException()
            else:
                with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                    pass
        except FanboxIconException:
            with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                pass
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                    pass
    
    response = redirect(join('/', 'banners', service, user), code=302)
    response.autocorrect_location_header = False
    return response
