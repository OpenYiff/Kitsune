import sys
import psycopg2
import datetime
import config
import json
import uuid
import logging

from indexer import index_artists
from gallery_dl import job
from gallery_dl import config as dlconfig
from gallery_dl.extractor.message import Message
from psycopg2.extras import RealDictCursor
from download import download_file, DownloaderException
from flag_check import check_for_flags
from proxy import get_proxy
from io import StringIO
from html.parser import HTMLParser
from os import makedirs
from os.path import join

from ..internals.database.database import get_conn
from ..lib.artist import delete_artist_cache_keys
from ..lib.post import delete_post_cache_keys

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = StringIO()
    def handle_data(self, d):
        self.text.write(d)
    def get_data(self):
        return self.text.getvalue()

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def import_posts(log_id, key):
    makedirs(join(config.download_path, 'logs'), exist_ok=True)
    sys.stdout = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')
    # sys.stderr = open(join(config.download_path, 'logs', f'{log_id}.log'), 'a')

    conn = get_conn()

    dlconfig.set(('output'), "mode", "null")
    dlconfig.set(('extractor', 'subscribestar'), "cookies", {
        "auth_token": key
    })
    dlconfig.set(('extractor', 'subscribestar'), "proxy", get_proxy())
    j = job.DataJob("https://subscribestar.adult/feed") 
    j.run()
    
    for message in j.data:
        try:
            if message[0] == Message.Directory:
                post = message[-1]

                file_directory = f"files/subscribestar/{post['author_name']}/{post['post_id']}"
                attachments_directory = f"attachments/subscribestar/{post['author_name']}/{post['post_id']}"
                
                cursor1 = conn.cursor()
                cursor1.execute("SELECT * FROM dnp WHERE id = %s AND service = 'subscribestar'", (post['author_name'],))
                bans = cursor1.fetchall()
                if len(bans) > 0:
                    print(f"Skipping ID {post['post_id']}: user {post['author_name']} is banned")
                    continue
                
                check_for_flags(
                    'subscribestar',
                    post['author_name'],
                    str(post['post_id'])
                )

                cursor2 = conn.cursor()
                cursor2.execute("SELECT * FROM posts WHERE id = %s AND service = 'subscribestar'", (str(post['post_id']),))
                existing_posts = cursor2.fetchall()
                if len(existing_posts) > 0:
                    continue

                print(f"Starting import: {post['post_id']}!")
                
                stripped_content = strip_tags(post['content'])
                post_model = {
                    'id': str(post['post_id']),
                    '"user"': post['author_name'],
                    'service': 'subscribestar',
                    'title': (stripped_content[:60] + '..') if len(stripped_content) > 60 else stripped_content,
                    'content': post['content'],
                    'embed': {},
                    'shared_file': False,
                    'added': datetime.datetime.now(),
                    'published': post['date'],
                    'edited': None,
                    'file': {},
                    'attachments': []
                }

                for attachment in list(filter(lambda msg: post['post_id'] == msg[-1]['post_id'] and msg[0] == Message.Url, j.data)):
                    if (len(post_model['file'].keys()) == 0):
                        filename, _ = download_file(
                            join(config.download_path, file_directory),
                            attachment[-1]['url'],
                            name = attachment[-1]['filename'] + '.' + attachment[-1]['extension']
                        )
                        post_model['file']['name'] = attachment[-1]['filename'] + '.' + attachment[-1]['extension']
                        post_model['file']['path'] = f'/{file_directory}/{filename}'
                    else:
                        filename, _ = download_file(
                            join(config.download_path, attachments_directory),
                            attachment[-1]['url'],
                            name = attachment[-1]['filename'] + '.' + attachment[-1]['extension']
                        )
                        post_model['attachments'].append({
                            'name': attachment[-1]['filename'] + '.' + attachment[-1]['extension'],
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

                delete_post_cache_keys

                print(f"Finished importing {post['post_id']}!")
        except Exception as e:
            print(f"Error while importing: {e}")
            conn.rollback()
            continue
    
    conn.close()
    print('Finished scanning for posts.')
    index_artists()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_posts(str(uuid.uuid4()), sys.argv[1])
    else:
        print('Argument required - Login token')