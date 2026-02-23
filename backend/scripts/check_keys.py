import os
import requests
from dotenv import load_dotenv
import logging

# Ensure we load backend/.env so this script accurately reports configured keys
load_dotenv()
logging.basicConfig(level=logging.INFO)

logging.info('SPRINGER_META_KEY set? %s', bool(os.getenv('SPRINGER_META_KEY')))
logging.info('SPRINGER_OPEN_ACCESS_KEY set? %s', bool(os.getenv('SPRINGER_OPEN_ACCESS_KEY')))
logging.info('NASA_ADS_TOKEN set? %s', bool(os.getenv('NASA_ADS_TOKEN')))
logging.info('IEEE_XPLORE_API_KEY set? %s', bool(os.getenv('IEEE_XPLORE_API_KEY')))

# Try Springer (Meta key preferred)
meta = os.getenv('SPRINGER_META_KEY') or os.getenv('SPRINGER_OPEN_ACCESS_KEY')
if meta:
    try:
        r = requests.get('https://api.springernature.com/meta/v2/json', params={'q':'gene','p':1,'api_key':meta}, timeout=15)
        logging.info('springer status %s', r.status_code)
        logging.debug('springer text: %s', r.text[:400].replace('\n',' '))
    except Exception as e:
        logging.exception('springer error')

# Try NASA ADS
ads = os.getenv('NASA_ADS_TOKEN')
if ads:
    try:
        r = requests.get('https://api.adsabs.harvard.edu/v1/search/query', params={'q':'star','fl':'bibcode','rows':1}, headers={'Authorization':f'Bearer {ads}'}, timeout=15)
        print('nasa status', r.status_code)
        print('nasa text:', r.text[:400].replace('\n',' '))
    except Exception as e:
        print('nasa error', e)

# Try IEEE Xplore quick check
ieee = os.getenv('IEEE_XPLORE_API_KEY')
if ieee:
    try:
        r = requests.get('https://ieeexploreapi.ieee.org/api/v1/search/articles', params={'querytext':'quantum','max_records':1,'apikey':ieee}, timeout=15)
        print('ieee status', r.status_code)
        print('ieee text:', r.text[:400].replace('\n',' '))
    except Exception as e:
        print('ieee error', e)
