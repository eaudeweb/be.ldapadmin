''' LDAP agent: values sent as bytes, values read back as str '''
import unittest
from unittest.mock import MagicMock as Mock, patch

import ldap

from be.ldapadmin.db_agent import BytesValuesMixin, UsersDB

USERS_DN = 'ou=Users,ou=DATA,ou=america,o=IRCusers,dc=CIRCA,dc=local'
ORGS_DN = 'ou=IRCorganisations,dc=CIRCA,dc=local'


class RecordingBase:
    def add_ext(self, dn, modlist, serverctrls=None, clientctrls=None):
        self.added = (dn, modlist)

    def modify_ext(self, dn, modlist, serverctrls=None, clientctrls=None):
        self.modified = (dn, modlist)


class RecordingConnection(BytesValuesMixin, RecordingBase):
    pass


class BytesValuesTest(unittest.TestCase):

    def test_add_encodes_values(self):
        conn = RecordingConnection()
        conn.add_ext('cn=dk_org,' + ORGS_DN, [
            ('objectClass', ['top', 'organizationGroup']),
            ('o', 'K\xf8benhavn club'),
            ('c', b'dk'),
        ])
        dn, modlist = conn.added
        self.assertEqual(dn, 'cn=dk_org,' + ORGS_DN)
        self.assertEqual(modlist, [
            ('objectClass', [b'top', b'organizationGroup']),
            ('o', ['K\xf8benhavn club'.encode('utf-8')]),
            ('c', [b'dk']),
        ])

    def test_modify_encodes_values_and_keeps_none(self):
        conn = RecordingConnection()
        conn.modify_ext('cn=dk_org,' + ORGS_DN, [
            (ldap.MOD_ADD, 'uniqueMember', ['uid=anne,' + USERS_DN]),
            (ldap.MOD_DELETE, 'telephoneNumber', None),
        ])
        dn, modlist = conn.modified
        self.assertEqual(modlist, [
            (ldap.MOD_ADD, 'uniqueMember', [b'uid=anne,' + USERS_DN.encode()]),
            (ldap.MOD_DELETE, 'telephoneNumber', None),
        ])


class ReadValuesTest(unittest.TestCase):

    def setUp(self):
        with patch.object(UsersDB, 'connect', return_value=Mock()):
            self.db = UsersDB(ldap_server='ldap.test')
        self.search = self.db.conn.search_s

    def test_all_organisations_decodes(self):
        self.search.return_value = [
            ('cn=dk_org,' + ORGS_DN, {'o': [b'K\xc3\xb8benhavn club'],
                                      'c': [b'dk']}),
        ]
        orgs = self.db.all_organisations()
        self.assertEqual(orgs['dk_org']['name'], 'K\xf8benhavn club')
        self.assertEqual(orgs['dk_org']['country'], 'dk')
        filterstr = self.search.call_args[1]['filterstr']
        self.assertIn('organizationGroup', filterstr)

    def test_members_in_org_skips_empty_members(self):
        self.search.return_value = [
            ('cn=dk_org,' + ORGS_DN, {'uniqueMember': [
                b'', ('uid=anne,' + USERS_DN).encode()]}),
        ]
        self.assertEqual(self.db.members_in_org('dk_org'), ['anne'])

    def test_orgs_for_user(self):
        self.search.return_value = [
            ('cn=dk_org,' + ORGS_DN, {'o': [b'K\xc3\xb8benhavn club']}),
        ]
        self.assertEqual(self.db.orgs_for_user('anne'),
                         [('dk_org', ['K\xf8benhavn club'])])
        filterstr = self.search.call_args[1]['filterstr']
        self.assertTrue(filterstr.startswith(
            '(&(objectClass=organizationGroup)(uniqueMember='))

    def test_existing_emails(self):
        self.search.return_value = [
            ('uid=anne,' + USERS_DN, {'mail': [b'anne@example.com']}),
        ]
        self.assertEqual(list(self.db.existing_emails(['anne@example.com'])),
                         ['anne@example.com'])

    def test_organisation_queries_use_organization_group(self):
        self.search.return_value = []
        self.db.search_org('club')
        self.db._search_user_in_orgs('anne')
        list(self.db.user_organisations('anne'))
        for call in self.search.call_args_list:
            self.assertNotIn('objectClass=organisation)',
                             call[1].get('filterstr', ''))
