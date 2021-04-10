import mimetypes
import requests
import uuid
import cgi
import re
import shutil
import functools
import urllib
from os import rename, makedirs
from os.path import join, getsize, exists, splitext, basename
from proxy import get_proxy

non_url_safe = ['"', '#', '$', '%', '&', '+',
    ',', '/', ':', ';', '=', '?',
    '@', '[', '\\', ']', '^', '`',
    '{', '|', '}', '~', "'"]

class DownloaderException(Exception):
    pass

def uniquify(path):
    filename, extension = splitext(path)
    counter = 1

    while exists(path.encode('utf-8')):
        path = filename + "_" + str(counter) + extension
        counter += 1

    return basename(path)

def get_filename_from_cd(cd):
    if not cd:
        return None
    fname = re.findall(r"filename\*=([^;]+)", cd, flags=re.IGNORECASE)
    if len(fname) == 0:
        return None
    if not fname:
        fname = re.findall("filename=([^;]+)", cd, flags=re.IGNORECASE)
    if "utf-8''" in fname[0].lower():
        fname = re.sub("utf-8''", '', fname[0], flags=re.IGNORECASE)
        fname = urllib.parse.unquote(fname)
    else:
        fname = fname[0]
    # clean space and double quotes
    return fname.strip().strip('"')

def slugify(text):
    """
    Turn the text content of a header into a slug for use in an ID
    """
    non_safe = [c for c in text if c in non_url_safe]
    if non_safe:
        for c in non_safe:
            text = text.replace(c, '')
    # Strip leading, trailing and multiple whitespace, convert remaining whitespace to _
    text = u'_'.join(text.split())
    return text

def download_file(ddir, url, name = None, **kwargs):
    temp_name = str(uuid.uuid4()) + '.temp'
    tries = 10
    makedirs(ddir, exist_ok=True)
    for i in range(tries):
        try:
            r = requests.get(url, stream = True, proxies=get_proxy(), **kwargs)
            r.raw.read = functools.partial(r.raw.read, decode_content=True)
            r.raise_for_status()
            # Should retry on connection error
            with open(join(ddir, temp_name), 'wb+') as file:
                shutil.copyfileobj(r.raw, file)
                # filename guessing
                mimetype, _ = cgi.parse_header(r.headers['content-type'])
                extension = mimetypes.guess_extension(mimetype, strict=False) if r.headers.get('content-type') else None
                extension = extension or '.txt'
                filename = name or r.headers.get('x-amz-meta-original-filename')
                if filename is None:
                    filename = get_filename_from_cd(r.headers.get('content-disposition')) or 'Untitled' + extension
                filename = slugify(filename)
                # ensure unique filename
                filename = uniquify(join(ddir, filename))
                # content integrity
                if r.headers.get('content-length') and r.raw.tell() < int(r.headers.get('content-length')):
                    reported_size = r.raw.tell()
                    downloaded_size = r.headers.get('content-length')
                    raise DownloaderException(f'Downloaded size is less than reported; {downloaded_size} < {reported_size}')
                
                file.close()
                rename(join(ddir, temp_name), join(ddir, filename))
                return filename, r
        except requests.HTTPError as e:
            raise e
        except:
            if i < tries - 1: # i is zero indexed
                continue
            else:
                raise
        break
