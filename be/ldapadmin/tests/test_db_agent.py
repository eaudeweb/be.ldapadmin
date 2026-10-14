''' LDAP agent: values sent as bytes, values read back as str '''
import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock as Mock, patch

import ldap

from be.ldapadmin.db_agent import (
    BytesValuesMixin, UsersDB, UserNotFound, RoleNotFound, NameAlreadyExists,
    EmailAlreadyExists, InvalidPermittedSender, DISABLE_ACCOUNT,
    parse_membership_type)

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


ROLES_DN = 'ou=DATA,ou=america,o=IRCroles,dc=CIRCA,dc=local'
ANNE_DN = 'uid=anne,' + USERS_DN
ORG_DN = 'cn=dk_org,' + ORGS_DN


def ldap_entries(entries):
    """ search_s side effect: SCOPE_BASE lookups in `entries` (dn -> attrs) """
    def search_s(dn, scope, filterstr=None, attrlist=None):
        if scope == ldap.SCOPE_BASE:
            if dn not in entries:
                raise ldap.NO_SUCH_OBJECT
            return [(dn, entries[dn])]
        return []
    return search_s


class AgentTestBase(unittest.TestCase):

    def setUp(self):
        with patch.object(UsersDB, 'connect', return_value=Mock()):
            self.db = UsersDB(ldap_server='ldap.test', author='admin')
        self.db._bound = True
        self.conn = self.db.conn
        self.conn.add_s.return_value = (ldap.RES_ADD, [])
        self.conn.modify_s.return_value = (ldap.RES_MODIFY, [])
        self.conn.delete_s.return_value = (ldap.RES_DELETE, [])
        self.conn.passwd_s.return_value = (ldap.RES_EXTENDED, [])
        self.conn.rename_s.return_value = (ldap.RES_MODRDN, [])

    def modifications(self, dn=None):
        return [c[0][1] for c in self.conn.modify_s.call_args_list
                if dn is None or c[0][0] == dn]

    def change_records(self, dn):
        """ metadata records saved on `dn` """
        out = []
        for mods in self.modifications(dn):
            for op, attr, value in mods:
                if attr == 'registeredAddress':
                    out.append(json.loads(value)[-1])
        return out


class UserInfoTest(AgentTestBase):

    def test_user_info(self):
        mt = UsersDB._encode_membership_type(None, 'places-bank', 'Member')
        self.conn.search_s.side_effect = lambda dn, scope, **kw: {
            ldap.SCOPE_BASE: [(ANNE_DN, {
                'givenName': [b'Ren\xc3\xa9'], 'sn': [b'Tester'],
                'cn': [b'Ren\xc3\xa9 Tester'],
                'mail': [b'anne@example.com', b'anne@example.org'],
                'o': [b'dk_org'], 'uid': [b'anne'],
                'destinationIndicator': [mt.encode()],
                'createTimestamp': [b'20100102030405Z'],
            })],
            ldap.SCOPE_ONELEVEL: [(ORG_DN, {})],
        }[scope]
        info = self.db.user_info('anne')
        self.assertEqual(info['id'], 'anne')
        self.assertEqual(info['first_name'], 'Ren\xe9')
        self.assertEqual(info['full_name'], 'Ren\xe9 Tester')
        self.assertEqual(info['email'], 'anne@example.com, anne@example.org')
        self.assertEqual(info['createTimestamp'], datetime(2010, 1, 2, 3, 4, 5))
        self.assertEqual(info['job_title'], '')
        self.assertEqual(info['orgs'], ['dk_org'])
        self.assertEqual(info['membership_type'], {'places-bank': 'Member'})

    def test_user_not_found(self):
        self.conn.search_s.side_effect = ldap.NO_SUCH_OBJECT
        with self.assertRaises(UserNotFound):
            self.db.user_info('nobody')

    def test_get_disabled_users(self):
        self.conn.search_s.return_value = [(ANNE_DN, {
            'cn': [b'Anne'], 'employeeType': [b'disabled'],
            'registeredAddress': [b'[]']})]
        users = self.db.get_disabled_users()
        self.assertEqual([(u['id'], u['status'], u['metadata'])
                          for u in users], [('anne', 'disabled', '[]')])

    def test_search_user_filter(self):
        self.conn.search_s.return_value = [(ANNE_DN, {'cn': [b'Anne T']})]
        users = self.db.search_user('Anne', ['uid', 'mail'], no_disabled=True)
        self.assertEqual(users[0]['full_name'], 'Anne T')
        self.assertEqual(
            self.conn.search_s.call_args[1]['filterstr'],
            '(&(objectClass=person)(!(employeeType=*disabled*))'
            '(|(uid=*anne*)(mail=*anne*)))')

    def test_custom_rdn_user_id(self):
        self.db._user_rdn = 'cn'
        dn = 'cn=Anne Tester,' + USERS_DN
        self.conn.search_s.side_effect = lambda base, scope, **kw: {
            ldap.SCOPE_ONELEVEL: [(dn, {})],
            ldap.SCOPE_BASE: [(dn, {'uid': [b'anne']})],
        }[scope]
        self.assertEqual(list(self.db.existing_usernames(['anne'])), ['anne'])


class CreateUserTest(AgentTestBase):

    def test_create_user(self):
        self.conn.search_s.return_value = []
        self.db.create_user('anne', {
            'first_name': 'Ren\xe9', 'last_name': 'Tester', 'job_title': '',
            'email': 'anne@example.com, anne@example.org'})
        dn, attrs = self.conn.add_s.call_args[0]
        self.assertEqual(dn, ANNE_DN)
        self.assertEqual(dict(attrs), {
            'objectClass': ['top', 'person', 'organizationalPerson',
                            'inetOrgPerson'],
            'uid': ['anne'], 'givenName': ['Ren\xe9'], 'sn': ['Tester'],
            'cn': ['Ren\xe9 Tester'],
        })
        self.assertEqual(self.modifications(ANNE_DN), [(
            (ldap.MOD_ADD, 'mail', ['anne@example.com']),
            (ldap.MOD_ADD, 'mail', ['anne@example.org']))])

    def test_existing_email(self):
        self.conn.search_s.return_value = [(ANNE_DN, {'uid': [b'anne']})]
        with self.assertRaises(EmailAlreadyExists):
            self.db.create_user('bob', {'first_name': 'Bob',
                                        'email': 'anne@example.com'})
        self.assertFalse(self.conn.add_s.called)

    def test_existing_name(self):
        self.conn.search_s.return_value = []
        self.conn.add_s.side_effect = ldap.ALREADY_EXISTS
        with self.assertRaises(NameAlreadyExists):
            self.db.create_user('anne', {'email': 'anne@example.com'})

    def test_set_user_password(self):
        with patch.object(UsersDB, 'user_info'):
            self.db.set_user_password('anne', None, 'secret')
        self.conn.passwd_s.assert_called_once_with(ANNE_DN, None, 'secret')


class SetUserInfoTest(AgentTestBase):

    def test_user_info_diff(self):
        old = {'first_name': 'Anne', 'last_name': 'Tester',
               'full_name': 'Anne Tester', 'job_title': 'Boss',
               'phone': '+45 1', 'email': 'anne@example.com',
               'membershipType': 'MT:x'}
        new = {'first_name': 'Anna', 'last_name': 'Tester',
               'job_title': '', 'phone': '+45 2', 'fax': '+45 3',
               'email': ['anne@example.org']}
        diff = self.db._user_info_diff('anne', old, new)
        self.assertEqual(sorted(diff[ANNE_DN], key=repr), sorted([
            (ldap.MOD_REPLACE, 'cn', ['Anna Tester']),
            (ldap.MOD_ADD, 'facsimileTelephoneNumber', ['+45 3']),
            (ldap.MOD_REPLACE, 'givenName', ['Anna']),
            (ldap.MOD_DELETE, 'mail', ['anne@example.com']),
            (ldap.MOD_ADD, 'mail', ['anne@example.org']),
            (ldap.MOD_REPLACE, 'telephoneNumber', ['+45 2']),
            (ldap.MOD_DELETE, 'title', []),
        ], key=repr))

    def test_set_user_info(self):
        old = {'first_name': 'Anne', 'last_name': 'Tester',
               'full_name': 'Anne Tester', 'email': 'anne@example.com',
               'organisation': 'free text org'}
        with patch.object(UsersDB, 'user_info', return_value=old), \
                patch.object(UsersDB, '_search_user_in_orgs',
                             return_value=['dk_org']), \
                patch.object(UsersDB, 'add_to_org') as add, \
                patch.object(UsersDB, 'remove_from_org') as remove:
            result = self.db.set_user_info('anne', {
                'first_name': 'Anne', 'last_name': 'Tester',
                'email': 'anne@example.com', 'organisation': ['se_org']})
        self.assertTrue(result)
        add.assert_called_once_with('se_org', ['anne'])
        self.assertEqual(sorted(c[0][0] for c in remove.call_args_list),
                         ['dk_org', 'free text org'])
        self.assertFalse(self.conn.modify_s.called)


class MetadataTest(AgentTestBase):

    def test_add_change_record(self):
        old = [{'action': 'X'}]
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {'registeredAddress': [json.dumps(old).encode()]}})
        with self.db.new_action():
            self.db.add_change_record(ANNE_DN, 'ADD_TO_ORG',
                                      {'organisation': 'dk_org'})
            action_id = self.db._v_action_id
        (op, attr, value), = self.modifications(ANNE_DN)[0]
        self.assertEqual((op, attr), (ldap.MOD_REPLACE, 'registeredAddress'))
        records = json.loads(value)
        self.assertEqual(records[0], {'action': 'X'})
        self.assertEqual(records[1]['action'], 'ADD_TO_ORG')
        self.assertEqual(records[1]['author'], 'admin')
        self.assertEqual(records[1]['action_id'], action_id)
        self.assertEqual(records[1]['data'], {'organisation': 'dk_org'})
        self.assertTrue(records[1]['timestamp'].endswith('+00:00'))

    def test_email_for_disabled_user(self):
        meta = [{'action': DISABLE_ACCOUNT, 'data': {'email': 'old@x.eu'}},
                {'action': DISABLE_ACCOUNT, 'data': {'email': 'new@x.eu'}},
                {'action': 'ENABLE_ACCOUNT', 'data': {}}]
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {'registeredAddress': [json.dumps(meta).encode()]}})
        self.assertEqual(self.db.get_email_for_disabled_user_dn(ANNE_DN),
                         'new@x.eu')


class DisableEnableTest(AgentTestBase):

    def test_disable_user(self):
        user = {'email': 'anne@example.com', 'membership_type': {'r': 'M'}}
        self.conn.search_s.side_effect = ldap_entries({ANNE_DN: {}})
        with patch.object(UsersDB, 'user_info', return_value=user), \
                patch.object(UsersDB, 'user_organisations',
                             return_value=iter([ORG_DN])), \
                patch.object(UsersDB, 'list_member_roles',
                             return_value=['places', 'places-bank']), \
                patch.object(UsersDB, 'remove_from_org') as remove_org, \
                patch.object(UsersDB, 'remove_from_role') as remove_role:
            remove_role.side_effect = [None, ValueError]
            self.db.disable_user('anne')
        remove_org.assert_called_once_with('dk_org', ['anne'])
        self.assertEqual(len(remove_role.call_args_list), 2)
        record, = self.change_records(ANNE_DN)
        self.assertEqual(record['action'], DISABLE_ACCOUNT)
        self.assertEqual(record['data']['organisations'], ['dk_org'])
        self.assertEqual(record['data']['roles'], ['places', 'places-bank'])
        self.assertEqual(record['data']['membership_type'], {'r': 'M'})
        self.assertIn((ldap.MOD_REPLACE, 'employeeType', 'disabled'),
                      self.modifications(ANNE_DN)[-1])
        dn, old_pw, new_pw = self.conn.passwd_s.call_args[0]
        self.assertEqual(len(new_pw), 20)

    def test_enable_user_restores_roles(self):
        meta = [{'action': DISABLE_ACCOUNT, 'data': {
            'email': 'anne@example.com', 'organisations': ['dk_org'],
            'roles': ['places-bank', 'gone'], 'roles_permittedPerson': [],
            'roles_owner': [], 'membership_type': {'places-bank': 'M'}}}]
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {'registeredAddress': [json.dumps(meta).encode()]}})
        with patch.object(UsersDB, 'add_to_org') as add_org, \
                patch.object(UsersDB, 'add_to_role') as add_role:
            add_role.side_effect = [None, ValueError]
            self.db.enable_user('anne', restore_roles=True)
        add_org.assert_called_once_with('dk_org', ['anne'])
        self.assertEqual(add_role.call_args_list[0][0],
                         ('places-bank', 'user', 'anne', 'M'))
        self.assertIn((ldap.MOD_REPLACE, 'employeeType', 'enabled'),
                      self.modifications(ANNE_DN)[-1])

    def test_enable_not_disabled_user(self):
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {'registeredAddress': [b'[]']}})
        with self.assertRaises(AssertionError):
            self.db.enable_user('anne')

    def test_delete_user(self):
        with patch.object(UsersDB, 'user_organisations',
                          return_value=iter([ORG_DN])), \
                patch.object(UsersDB, 'list_member_roles', return_value=[]), \
                patch.object(UsersDB, 'remove_from_org') as remove_org:
            self.db.delete_user('anne')
        remove_org.assert_called_once_with('dk_org', ['anne'])
        self.conn.delete_s.assert_called_once_with(ANNE_DN)


class OrganisationsTest(AgentTestBase):

    def test_org_info(self):
        self.conn.search_s.side_effect = ldap_entries({ORG_DN: {
            'o': [b'K\xc3\xb8benhavn club'], 'c': [b'dk'],
            'labeledURI': [b'http://k.dk']}})
        info = self.db.org_info('dk_org')
        self.assertEqual((info['id'], info['name'], info['country'],
                          info['url'], info['phone']),
                         ('dk_org', 'K\xf8benhavn club', 'dk',
                          'http://k.dk', ''))
        self.assertEqual(self.db.org_info('se_org')['id'],
                         'INEXISTENT ORGANISATION se_org')

    def test_create_org(self):
        self.conn.search_s.side_effect = ldap_entries({ORG_DN: {}})
        self.db.create_org('dk_org', {'name': 'K\xf8benhavn', 'url': '',
                                      'country': 'dk'})
        dn, attrs = self.conn.add_s.call_args[0]
        self.assertEqual(dn, ORG_DN)
        attrs = dict(attrs)
        self.assertEqual(attrs['o'], ['K\xf8benhavn'])
        self.assertEqual(attrs['c'], ['dk'])
        self.assertEqual(attrs['uniqueMember'], [''])
        self.assertNotIn('labeledURI', attrs)
        self.assertEqual(self.change_records(ORG_DN)[0]['action'],
                         'CREATED_ORG')

    def test_set_org_info(self):
        self.conn.search_s.side_effect = ldap_entries({ORG_DN: {
            'o': [b'Old'], 'c': [b'dk'], 'mail': [b'a@b.dk']}})
        self.db.set_org_info('dk_org', {'name': 'New', 'country': 'dk',
                                        'url': 'http://n.dk'})
        changes = sorted(self.modifications(ORG_DN)[0], key=repr)
        self.assertEqual(changes, sorted([
            (ldap.MOD_REPLACE, 'o', ['New']),
            (ldap.MOD_ADD, 'labeledURI', ['http://n.dk']),
            (ldap.MOD_DELETE, 'mail', []),
        ], key=repr))

    def test_add_to_empty_org(self):
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {}, ORG_DN: {'uniqueMember': [b'']}})
        self.db.add_to_org('dk_org', ['anne'])
        self.assertEqual(self.modifications(ANNE_DN)[0],
                         ((ldap.MOD_ADD, 'o', ['dk_org']),))
        self.assertIn(((ldap.MOD_ADD, 'uniqueMember', [ANNE_DN]),
                       (ldap.MOD_DELETE, 'uniqueMember', [''])),
                      self.modifications(ORG_DN))
        self.assertEqual(self.change_records(ANNE_DN)[0]['data'],
                         {'organisation': 'dk_org'})

    def test_remove_last_member_from_org(self):
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {}, ORG_DN: {'uniqueMember': [ANNE_DN.encode()]}})
        self.db.remove_from_org('dk_org', ['anne'])
        self.assertIn(((ldap.MOD_ADD, 'uniqueMember', ['']),
                       (ldap.MOD_DELETE, 'uniqueMember', [ANNE_DN])),
                      self.modifications(ORG_DN))
        self.assertIn(((ldap.MOD_DELETE, 'o', ['dk_org']),),
                      self.modifications(ANNE_DN))

    def test_remove_from_org_value_already_gone(self):
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {}, ORG_DN: {'uniqueMember': [ANNE_DN.encode(),
                                  ('uid=bob,' + USERS_DN).encode()]}})

        def modify_s(dn, changes):
            if dn == ORG_DN and changes[0][1] == 'uniqueMember':
                raise ldap.NO_SUCH_ATTRIBUTE({'info': 'no such value'})
            return (ldap.RES_MODIFY, [])
        self.conn.modify_s.side_effect = modify_s
        self.db.remove_from_org('dk_org', ['anne'])
        self.assertIn(((ldap.MOD_DELETE, 'o', ['dk_org']),),
                      self.modifications(ANNE_DN))

    def test_pending_members(self):
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {}, ORG_DN: {'pendingUniqueMember': [ANNE_DN.encode()]}})
        self.assertEqual(self.db.pending_members_in_org('dk_org'), ['anne'])
        self.db.add_pending_to_org('dk_org', ['anne'])
        self.assertIn(((ldap.MOD_ADD, 'pendingUniqueMember', [ANNE_DN]),),
                      self.modifications(ORG_DN))

    def test_rename_org(self):
        role_dn = 'ou=places,' + ROLES_DN
        new_dn = 'cn=se_org,' + ORGS_DN
        self.conn.search_s.side_effect = lambda base, scope, **kw: (
            [(role_dn, {})] if scope == ldap.SCOPE_SUBTREE
            else [(new_dn, {})])
        self.db.rename_org('dk_org', 'se_org')
        self.conn.rename_s.assert_called_once_with(ORG_DN, 'cn=se_org')
        self.assertEqual(self.modifications(role_dn), [(
            (ldap.MOD_DELETE, 'uniqueMember', [ORG_DN]),
            (ldap.MOD_ADD, 'uniqueMember', [new_dn]))])
        self.assertEqual(self.change_records(new_dn)[0]['data'],
                         {'old_name': 'dk_org'})

    def test_org_exists(self):
        self.conn.search_s.side_effect = ldap_entries({ORG_DN: {}})
        self.assertTrue(self.db.org_exists('dk_org'))
        self.assertFalse(self.db.org_exists('se_org'))
        self.assertIsNone(self.db.org_exists(''))


class RolesTest(AgentTestBase):

    def test_role_info(self):
        self.conn.search_s.return_value = [('ou=places,' + ROLES_DN, {
            'description': [b'Pl\xc3\xa4ces'], 'postalAddress': [b'a$b'],
            'l': [b'deactivated:true'], 'businessCategory': [b'True'],
            'owner': [ANNE_DN.encode()]})]
        info = self.db.role_info('places')
        self.assertEqual(info['description'], 'Pl\xe4ces')
        self.assertEqual(info['postalAddress'], 'a\nb')
        self.assertTrue(info['isDeactivated'])
        self.assertTrue(info['extendedManagement'])
        self.assertEqual(info['owner'], [ANNE_DN])

    def test_role_not_found(self):
        self.conn.search_s.side_effect = ldap.NO_SUCH_OBJECT
        with self.assertRaises(RoleNotFound):
            self.db.role_info('places')
        self.assertFalse(self.db.role_exists('places'))

    def test_members_in_role(self):
        role_dn = 'ou=places,' + ROLES_DN
        sub_dn = 'ou=places-bank,' + role_dn
        self.conn.search_s.side_effect = lambda dn, scope, **kw: {
            ldap.SCOPE_BASE: [(role_dn, {'uniqueMember': [
                b'', ANNE_DN.encode(), ('uid=bob,' + USERS_DN).encode(),
                ORG_DN.encode()]})],
            ldap.SCOPE_ONELEVEL: [(sub_dn, {'uniqueMember': [
                ('uid=bob,' + USERS_DN).encode()]})],
        }[scope]
        members = self.db.members_in_role('places')
        self.assertEqual(members, {'users': ['anne'], 'orgs': ['dk_org']})
        members = self.db.members_in_role_and_subroles('places')
        self.assertEqual(members, {'users': ['anne', 'bob'],
                                   'orgs': ['dk_org']})

    def test_members_in_subroles_with_source(self):
        role_dn = 'ou=places,' + ROLES_DN
        sub_dn = 'ou=places-bank,' + role_dn
        bob = 'uid=bob,' + USERS_DN
        self.conn.search_s.return_value = [
            (sub_dn, {'uniqueMember': [bob.encode()]}),
            (role_dn, {'uniqueMember': [ANNE_DN.encode(), bob.encode()]}),
        ]
        members = self.db.members_in_subroles_with_source('places')
        self.assertEqual(dict(members['users']), {
            'anne': ['places'], 'bob': ['places-bank']})

    def test_filter_roles(self):
        self.conn.search_s.return_value = [
            (ROLES_DN, {}),
            ('ou=places,' + ROLES_DN, {}),
            ('ou=places-bank,ou=places,' + ROLES_DN, {}),
            ('ou=shops-bank,ou=shops,' + ROLES_DN, {}),
        ]
        roles = self.db.filter_roles('*-bank')
        self.assertEqual([r for r, attrs in roles],
                         ['places-bank', 'shops-bank'])
        self.assertEqual(self.db.filter_roles('caf\xe9'), set())

    def test_role_names_in_role(self):
        self.conn.search_s.return_value = [
            ('ou=places-bank,ou=places,' + ROLES_DN,
             {'description': [b'B\xc3\xa4nk']}),
            ('ou=places-shop,ou=places,' + ROLES_DN, {}),
        ]
        self.assertEqual(self.db.role_names_in_role('places'),
                         {'places-bank': 'B\xe4nk', 'places-shop': ''})

    def test_create_role(self):
        self.db.create_role('places-bank', 'Bank')
        dn, attrs = self.conn.add_s.call_args[0]
        self.assertEqual(dn, 'ou=places-bank,ou=places,' + ROLES_DN)
        self.assertEqual(dict(attrs)['ou'], ['bank'])
        self.assertEqual(dict(attrs)['description'], ['Bank'])
        self.conn.add_s.side_effect = ldap.NO_SUCH_OBJECT
        with self.assertRaises(ValueError):
            self.db.create_role('nowhere-bank', 'Bank')

    def test_set_role_status(self):
        role_dn = 'ou=places,' + ROLES_DN

        def modify_s(dn, changes):
            if changes[0][0] == ldap.MOD_REPLACE:
                raise ldap.NO_SUCH_ATTRIBUTE
            return (ldap.RES_MODIFY, [])
        self.conn.modify_s.side_effect = modify_s
        self.db.set_role_status('places', 'Terminated')
        self.db.set_role_status('places', '')
        self.db.deactivate_role('places')
        self.assertEqual(self.modifications(role_dn), [
            ((ldap.MOD_REPLACE, 'postOfficeBox', ['Terminated']),),
            ((ldap.MOD_ADD, 'postOfficeBox', ['Terminated']),),
            ((ldap.MOD_DELETE, 'postOfficeBox', []),),
            ((ldap.MOD_REPLACE, 'l', ['deactivated:true']),),
            ((ldap.MOD_ADD, 'l', ['deactivated:true']),),
        ])

    def test_add_to_role(self):
        role_dn = 'ou=places-bank,ou=places,' + ROLES_DN
        self.conn.search_s.side_effect = ldap_entries({
            ANNE_DN: {}, role_dn: {}, 'ou=places,' + ROLES_DN: {}})
        with patch.object(UsersDB, 'set_membership_type') as set_mt:
            roles = self.db.add_to_role('places-bank', 'user', 'anne', 'M')
        self.assertEqual(roles, ['places', 'places-bank'])
        set_mt.assert_called_once_with('places-bank', 'anne', 'M')
        self.assertIn(((ldap.MOD_ADD, 'uniqueMember', [ANNE_DN]),),
                      self.modifications(role_dn))
        records = [r['data'] for r in self.change_records(ANNE_DN)]
        self.assertEqual(records, [
            {'role': 'places', 'member_type': 'user'},
            {'role': 'places-bank', 'member_type': 'user',
             'membership_type': 'M'}])

    def test_set_membership_type(self):
        old = UsersDB._encode_membership_type(None, 'places', 'Old')
        with patch.object(UsersDB, 'user_info', return_value={
                'membership_type': parse_membership_type(old)}):
            result = self.db.set_membership_type('places-bank', 'anne', 'M')
        self.assertEqual(result, (None, 'M'))
        (op, attr, values), = self.modifications(ANNE_DN)[0]
        self.assertEqual((op, attr), (ldap.MOD_REPLACE,
                                      'destinationIndicator'))
        self.assertEqual(parse_membership_type(', '.join(values)),
                         {'places': 'Old', 'places-bank': 'M'})

    def test_mail_group_info(self):
        self.conn.search_s.return_value = [('ou=places,' + ROLES_DN, {
            'owner': [ANNE_DN.encode()],
            'permittedPerson': [('uid=bob,' + USERS_DN).encode()],
            'permittedSender': [b'members']})]
        self.assertEqual(self.db.mail_group_info('places'), {
            'owner': ['anne'], 'permittedPerson': ['bob'],
            'permittedSender': ['members']})

    def test_remove_permitted_person(self):
        role_dn = 'ou=places,' + ROLES_DN
        self.conn.search_s.side_effect = ldap_entries({ANNE_DN: {}})
        self.db.remove_permittedPerson('places', 'anne')
        self.assertEqual(self.modifications(role_dn), [
            ((ldap.MOD_DELETE, 'permittedPerson', [ANNE_DN]),)])
        self.assertEqual(self.change_records(ANNE_DN)[0]['data'],
                         {'role': 'places'})

    def test_add_permitted_sender(self):
        role_dn = 'ou=places,' + ROLES_DN
        self.conn.search_s.side_effect = ldap_entries({role_dn: {}})
        self.db.add_permittedSender('places', 'owners')
        self.assertEqual(self.modifications(role_dn), [
            ((ldap.MOD_ADD, 'permittedSender', ['owners']),)])
        with self.assertRaises(InvalidPermittedSender):
            self.db.add_permittedSender('places', 'nobody')

    def test_role_owner(self):
        role_dn = 'ou=places,' + ROLES_DN
        sub_dn = 'ou=places-bank,' + role_dn

        def search_s(dn, scope, filterstr='', **kw):
            if dn == ANNE_DN:
                return [(dn, {})]
            if 'owner=' in filterstr:
                return [(role_dn, {})]
            return [(role_dn, {}), (sub_dn, {})]
        self.conn.search_s.side_effect = search_s
        self.assertEqual(self.db.add_role_owner('places', 'anne'),
                         ['places-bank'])
        self.assertEqual(self.modifications(sub_dn),
                         [((ldap.MOD_ADD, 'owner', [ANNE_DN]),)])
        self.assertEqual(self.db.remove_role_owner('places', 'anne'),
                         ['places'])

    def test_list_member_roles(self):
        self.conn.search_s.return_value = [
            ('ou=places,' + ROLES_DN, {}),
            ('ou=places-bank,ou=places,' + ROLES_DN, {})]
        self.assertEqual(self.db.list_member_roles('user', 'anne'),
                         ['places', 'places-bank'])
        roles = list(self.db.member_roles_info('org', 'dk_org'))
        self.assertEqual([r for r, attrs in roles], ['places', 'places-bank'])
        self.assertIn(ORG_DN, self.conn.search_s.call_args[1]['filterstr'])

    def test_all_roles(self):
        top = 'ou=places,' + ROLES_DN
        sub = 'ou=places-bank,' + top
        children = {ROLES_DN: [(top, {})], top: [(sub, {})], sub: []}
        self.conn.search_s.side_effect = lambda dn, scope, **kw: (
            children[dn] if scope == ldap.SCOPE_ONELEVEL
            else [(dn, {'description': [dn.split(',')[0].encode()]})])
        roles = self.db.all_roles()
        self.assertEqual([(dn, info['description']) for dn, info in roles],
                         [(top, 'ou=places'), (sub, 'ou=places-bank')])


class PictureTest(AgentTestBase):

    def test_profile_picture(self):
        self.conn.search_s.return_value = [(ANNE_DN, {'jpegPhoto': [b'\xff']})]
        self.assertEqual(self.db.get_profile_picture('anne'), b'\xff')
        self.conn.search_s.return_value = [(ANNE_DN, {})]
        self.assertIsNone(self.db.get_certificate('anne'))

    def test_set_user_picture(self):
        def modify_s(dn, changes):
            if changes[0][0] == ldap.MOD_REPLACE:
                raise ldap.NO_SUCH_ATTRIBUTE
            return (ldap.RES_MODIFY, [])
        self.conn.modify_s.side_effect = modify_s
        self.assertTrue(self.db.set_user_picture('anne', b'\xff\xd8'))
        self.assertTrue(self.db.set_user_picture('anne', None))
        self.assertEqual(self.modifications(ANNE_DN), [
            ((ldap.MOD_REPLACE, 'jpegPhoto', [b'\xff\xd8']),),
            ((ldap.MOD_ADD, 'jpegPhoto', [b'\xff\xd8']),),
            ((ldap.MOD_DELETE, 'jpegPhoto', None),),
        ])
