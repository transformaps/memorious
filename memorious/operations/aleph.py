import json
import requests
from banal import clean_dict
from urlparse import urljoin

from memorious import settings


def aleph_emit(context, data):
    context.log.info("Store [aleph]: %s", data.get('url'))
    if not settings.ALEPH_HOST:
        context.log.warning("No $MEMORIOUS_ALEPH_HOST, skipping upload...")
        return
    if not settings.ALEPH_API_KEY:
        context.log.warning("No $MEMORIOUS_ALEPH_API_KEY, skipping upload...")
        return

    with context.http.rehash(data) as result:
        if not result.ok:
            return
        submit_result(context, result, data)


def submit_result(context, result, data):
    if result.file_path is None:
        context.log.info("Cannot ingest non-existant response: %s", result)
        return

    session = requests.Session()
    session.headers['Authorization'] = 'apikey %s' % settings.ALEPH_API_KEY
    collection_id = get_collection_id(context, session)
    meta = {
        'crawler': context.crawler.name,
        'source_url': data.get('source_url', result.url),
        'file_name': data.get('file_name', result.file_name),
        'title': data.get('title'),
        'author': data.get('author'),
        'foreign_id': data.get('foreign_id', result.request_id),
        'mime_type': data.get('mime_type', result.content_type),
        'countries': data.get('countries'),
        'languages': data.get('languages'),
        'headers': dict(result.headers or {})
    }
    meta = clean_dict(meta)
    url = make_url('collections/%s/ingest' % collection_id)
    title = meta.get('title', meta.get('file_name', meta.get('source_url')))
    context.log.info("Sending '%s' to %s", title, url)
    res = session.post(url,
                       data={'meta': json.dumps(meta)},
                       files={'file': open(result.file_path, 'rb')})
    if not res.ok:
        context.emit_warning("Could not ingest '%s': %r" % (title, res.text))
    else:
        document = res.json().get('documents')[0]
        context.log.info("Ingesting, document ID: %s", document['id'])


def get_collection_id(context, session):
    url = make_url('collections')
    foreign_id = context.get('collection', context.crawler.name)
    while True:
        res = session.get(url, params={'limit': 100})
        data = res.json()
        for coll in data.get('results'):
            if coll.get('foreign_id') == foreign_id:
                return coll.get('id')
        if not data.get('next_url'):
            break
        url = urljoin(url, data.get('next_url'))

    url = make_url('collections')
    res = session.post(url, json={
        'label': context.crawler.description,
        'managed': True,
        'foreign_id': foreign_id
    })
    return res.json().get('id')


def make_url(path):
    return urljoin(settings.ALEPH_HOST, '/api/1/%s' % path)
