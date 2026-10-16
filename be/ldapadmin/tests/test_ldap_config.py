''' LDAP agent built from the saved configuration '''
import unittest
from unittest.mock import patch

from be.ldapadmin.ldap_config import defaults, ldap_agent_with_config

CONFIG = {
    'ldap_server': 'ldap.test',
    'users_dn': 'ou=Users,dc=test',
    'roles_dn': 'ou=Roles,dc=test',
}


class LdapAgentWithConfigTest(unittest.TestCase):

    @patch('be.ldapadmin.ldap_config.UsersDB')
    def test_config_without_orgs_dn(self, users_db):
        ldap_agent_with_config(CONFIG)
        kwargs = users_db.call_args[1]
        self.assertEqual(kwargs['orgs_dn'], defaults['orgs_dn'])
        self.assertEqual(kwargs['users_rdn'], defaults['users_rdn'])

    @patch('be.ldapadmin.ldap_config.UsersDB')
    def test_config_with_orgs_dn(self, users_db):
        ldap_agent_with_config(dict(CONFIG, orgs_dn='ou=Orgs,dc=test'))
        self.assertEqual(users_db.call_args[1]['orgs_dn'], 'ou=Orgs,dc=test')
