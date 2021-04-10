from flask import Blueprint, redirect, current_app

from ..internals.download import download_file

banners = Blueprint('banners', __name__)

@banners.route('/banners/<service>/<user>')
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
                    raise BannerException()
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
                    raise BannerException()
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
                    raise BannerException()
            else:
                with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                    pass
        except BannerException:
            current_app.logger.exception(f'Error importing banner for {user_id} on {service}')
            with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                pass
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                with open(join(config.download_path, 'banners', service, user), 'w') as _: 
                    pass
            else:
                current_app.logger.exception(f'HTTP error importing banner for {user_id} on {service}')
    
    response = redirect(join('/', 'banners', service, user), code=302)
    response.autocorrect_location_header = False
    return response

class BannerException(Exception):
    pass
