from dotenv import load_dotenv
import os, requests, traceback, logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
key = os.getenv('SPRINGER_META_KEY') or os.getenv('SPRINGER_OPEN_ACCESS_KEY')
resp = requests.get('https://api.springernature.com/meta/v2/json', params={'q':'gene','p':3,'api_key':key}, timeout=30)
logging.info('status %s', resp.status_code)
data = resp.json()

records = data.get('records', [])
logging.info('records_count %d', len(records))

for i, item in enumerate(records[:20]):
    try:
        creators = item.get('creators') or []
        authors = [c.get('creator', '') for c in creators]
        abstract = item.get('abstract') or 'No abstract available.'
        published = (item.get('publicationDate') or item.get('onlineDate') or '')[:10]
        doi = item.get('doi') or ''
        raw_url = item.get('url')
        url_val = ''
        if doi:
            url_val = f"https://doi.org/{doi}"
        else:
            if isinstance(raw_url, list) and raw_url:
                first = raw_url[0]
                if isinstance(first, dict):
                    url_val = first.get('value', '') or ''
                else:
                    url_val = str(first)
            elif isinstance(raw_url, dict):
                url_val = raw_url.get('value', '') or ''
            elif isinstance(raw_url, str):
                url_val = raw_url
            else:
                url_val = ''
        subjects = []
        raw_subjects = item.get('subjects') or []
        if isinstance(raw_subjects, list):
            subjects = [s.get('term', '') if isinstance(s, dict) else str(s) for s in raw_subjects]
        elif isinstance(raw_subjects, dict):
            subjects = [raw_subjects.get('term', '')]
        elif isinstance(raw_subjects, str):
            subjects = [raw_subjects]

        pub_name = item.get('publicationName') or ''
        categories = ([pub_name] if pub_name else []) + subjects[:2]
        logging.info('%d ok %s url=%s', i, (item.get('title') or '')[:40], url_val[:80])
    except Exception:
        logging.exception('EXC in record %d', i)
        traceback.print_exc()
