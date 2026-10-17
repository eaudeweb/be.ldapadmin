''' countries module '''


import os.path
import json
import logging


logger = logging.getLogger(__name__)

_country_storage = {
    'time': 0,
    'data': {},
    'timeout': 3600 * 24,  # seconds
}
COUNTRIES = _country_storage['data']  # shortcut

DUMMY = {'code': '',
         'name': '',
         'pub_code': '',
         }


def load_countries():
    """ Load the EU countries from countries.json in this package """
    global COUNTRIES
    with open(os.path.join(os.path.dirname(__file__), "countries.json"),
              encoding="utf-8") as f:
        data = json.load(f)
    COUNTRIES = {}
    COUNTRIES.update([(x['code'], x) for x in data])
    return data


def get_country(code):
    """ Return country object for given code """
    code = code.lower()
    return COUNTRIES.get(code.lower(), DUMMY)


def get_country_options(country=None):
    """ Return the list of options for country field. Pseudo-countries first,
    then countries sorted by name """
    if country:
        country = [country]
    countries = list(COUNTRIES.items())
    if country:
        return [country_data for country_data in countries
                if country_data[0] in country]
    countries.sort(key=lambda x: x[1]['name'])
    return countries
