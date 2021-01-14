''' countries module '''


import os.path
import json
import logging

from constants import LDAP_DISK_STORAGE

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
    """ Load countries from json file in memory """
    global COUNTRIES
    try:
        f = open(os.path.join(LDAP_DISK_STORAGE, "countries.json"), "r")
        f.close()
    except (IOError, ValueError):
        raise
    else:
        f = open(os.path.join(LDAP_DISK_STORAGE, "countries.json"), "r")
        data = json.load(f)
        f.close()
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
    countries = COUNTRIES.items()
    if country:
        return [country_data for country_data in countries
                if country_data[0] in country]
    countries.sort(key=lambda x: x[1]['name'])
    return countries
