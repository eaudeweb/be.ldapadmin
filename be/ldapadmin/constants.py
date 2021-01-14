''' constants '''

import os

from App.config import getConfiguration

cfg = getConfiguration()
cfg.environment.update(os.environ)

# constant defined in env
NETWORK_NAME = getattr(cfg, 'environment', {}).get('NETWORK_NAME',
                                                   'Environment Belgium')
NETWORK_URL = getattr(cfg, 'environment', {}).get(
    'NETWORK_URL', 'https://envcoord.health.fgov.be')
BASE_DOMAIN = getattr(cfg, 'environment', {}).get('BASE_DOMAIN',
                                                  'envcoord.health.fgov.be')
ADDR_FROM = getattr(cfg, 'environment', {}).get(
    'ADDR_FROM', 'no-reply@envcoord.health.fgov.be')
HELPDESK_EMAIL = getattr(cfg, 'environment', {}).get(
    'HELPDESK_EMAIL', 'helpdesk@envcoord.health.fgov.be')
LDAP_DISK_STORAGE = getattr(cfg, 'environment', {}).get(
    'LDAP_DISK_STORAGE', os.environ.get('LDAP_DISK_STORAGE', ''))
LDAP_DB_NAME = getattr(cfg, 'environment', {}).get(
    'LDAP_DB_NAME', os.environ.get('LDAP_DB_NAME', ''))

USER_INFO_KEYS = [
    'status', 'last_name', 'uid', 'reasonToCreate', 'full_name', 'id',
    'first_name', 'organisation', 'department', 'email', 'metadata', 'dn',
    'fax', 'postal_address', 'phone', 'employeeNumber', 'modifyTimestamp',
    'mobile', 'full_name_native', 'pwdChangedTime', 'url', 'createTimestamp',
    'job_title', 'search_helper']
