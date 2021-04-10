from flask import Blueprint, request
from ..internals.utils.utils import get_import_id

api = Blueprint('api', __name__)

@api.route('/api/import', methods=['POST'])
def import_api():
    key = request.args.get('session_key')
    import_id = get_import_id(key)

    if not key:
        return "", 401
    if request.args.get('service') == 'patreon':
        th = threading.Thread(target=patreon.import_posts, args=(import_id, key))
        th.start()
    elif request.args.get('service') == 'fanbox':
        th = threading.Thread(target=fanbox.import_posts, args=(import_id, key))
        th.start()
    elif request.args.get('service') == 'subscribestar':
        th = threading.Thread(target=subscribestar.import_posts, args=(import_id, key))
        th.start()
    elif request.args.get('service') == 'gumroad':
        th = threading.Thread(target=gumroad.import_posts, args=(import_id, key))
        th.start()
    return import_id, 200
