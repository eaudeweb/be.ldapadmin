''' Agent built from an LDAP User Folder '''
import unittest
from unittest.mock import Mock, patch

from be.ldapadmin.factories import LDAPUnavailable, agent_from_uf


class AgentFromUfTest(unittest.TestCase):

    def make_folder(self, server):
        folder = Mock(users_base='ou=Users,dc=test',
                      groups_base='ou=Roles,dc=test')
        folder.getCurrentServer.return_value = server
        return folder

    @patch('be.ldapadmin.factories.UsersDB')
    def test_connected_server(self, users_db):
        agent_from_uf(self.make_folder('ldap://ldap.test:389'))
        kwargs = users_db.call_args[1]
        self.assertEqual(kwargs['ldap_server'], 'ldap.test:389')
        self.assertEqual(kwargs['users_dn'], 'ou=Users,dc=test')

    @patch('be.ldapadmin.factories.UsersDB')
    def test_not_connected(self, users_db):
        folder = self.make_folder('-- not connected --')
        with self.assertRaises(LDAPUnavailable) as cm:
            agent_from_uf(folder)
        self.assertIn('not connected', str(cm.exception))
        self.assertFalse(users_db.called)
