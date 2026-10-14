''' user ids generated for imported users '''
import unittest
from unittest.mock import Mock

from be.ldapadmin.users_admin import generate_user_id


def agent_with(existing):
    agent = Mock()
    agent.existing_usernames.side_effect = lambda ids: [i for i in ids
                                                        if i in existing]
    return agent


class GenerateUserIdTest(unittest.TestCase):

    def test_base_uid(self):
        self.assertEqual(generate_user_id('Anne', 'Tester', agent_with([]), []),
                         'testeann')

    def test_short_first_name(self):
        self.assertEqual(generate_user_id('Al', 'Tester', agent_with([]), []),
                         'testeral')

    def test_taken_uid_gets_a_letter(self):
        uid = generate_user_id('Anne', 'Tester', agent_with(['testeann']),
                               ['testeana'])
        self.assertEqual(uid, 'testeanb')
