""" integration with naaya.ldapdump """

import logging
import os.path
import sqlite3
from unidecode import unidecode
from zope.component import getUtility

from naaya.ldapdump import main
from naaya.ldapdump.interfaces import IDumpReader
from be.ldapadmin.constants import LDAP_DISK_STORAGE, LDAP_DB_NAME
from be.ldapadmin.constants import ORGS_SPECIFIC

log = logging.getLogger(__name__)


def dump_ldap(ldap_logging_path):
    """ Perform a dump of an LDAP database according to the config file. """
    naaya_ldap_cfg = os.path.join(ldap_logging_path, 'config.yaml')
    if os.path.exists(naaya_ldap_cfg):
        return main.dump_ldap(naaya_ldap_cfg)
    return None


def get_objects_by_ldap_dump(specific):
    DB_FILE = os.path.join(LDAP_DISK_STORAGE, LDAP_DB_NAME)
    if not os.path.exists(DB_FILE):
        util = getUtility(IDumpReader)
        DB_FILE = util.db_path
        assert os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT a.dn as dn, a.value AS cn "
        "FROM ldapmapping a WHERE a.attr = 'cn' "
    )

    ldap_user_records = []
    for data in cursor.fetchall():
        if specific in data['dn']:
            try:
                ldap_user_records.append({'dn': data['dn'],
                                          'cn': unidecode(data['cn']),
                                          'o': unidecode(data.get('o'))})
            except AttributeError:
                ldap_user_records.append({'dn': data['dn'],
                                          'cn': unidecode(data['cn'])})

    return ldap_user_records


def get_org_by_ldap_dump(org_id):
    dn_prefix = 'cn='
    dn_suffix = (',ou=IRCorganisations,dc=CIRCA,'
                 'dc=local')
    org_dn = dn_prefix + org_id.strip() + dn_suffix
    orgs = get_objects_by_ldap_dump(ORGS_SPECIFIC)
    org_info = [info for info in orgs if info['dn'] == org_dn]
    if org_info:
        return org_info[0]
    else:
        return {}
