''' Roles import from .xlsx and .xls files '''
import unittest
from io import BytesIO
from unittest.mock import MagicMock as Mock

from be.ldapadmin.tests.test_excel_reader import build_xls, build_xlsx
from be.ldapadmin.tests.test_roles_ui import (
    StubbedRolesEditor, mock_request)

SHEETS = [
    [['role', 'description'], ['dk-new', 'New role'], ['', ''],
     ['dk-other', 'Other']],
    [['role', 'description'], ['dk-old', ' Renamed ']],
    [['from', 'to'], ['dk-a', 'dk-b']],
    [['to fill', 'template'], ['dk-c', 'dk-d']],
]


class ImportRolesTest(unittest.TestCase):

    def run_import(self, data):
        ui = StubbedRolesEditor()
        ui._create_roles = Mock(return_value=[])
        request = mock_request()
        request.form = {'file': BytesIO(data)}
        ui.REQUEST = request
        return ui, ui.import_xls(request)

    def test_import_xlsx(self):
        ui, result = self.run_import(build_xlsx(SHEETS))
        ui._create_roles.assert_called_once_with(
            {'dk-new': 'New role', 'dk-other': 'Other'})
        self.assertIsNotNone(result)

    def test_xls_rejected(self):
        ui, result = self.run_import(build_xls(SHEETS))
        self.assertIn('Not a valid file', result)
        self.assertFalse(ui._create_roles.called)

    def test_invalid_file(self):
        ui = StubbedRolesEditor()
        request = mock_request()
        request.form = {'file': BytesIO(b'not excel')}
        ui.REQUEST = request
        self.assertIn('Not a valid file', ui.import_xls(request))


class CreateRolesTest(unittest.TestCase):

    def test_no_owner_added(self):
        ui = StubbedRolesEditor()
        agent = Mock()
        ui._get_ldap_agent = Mock(return_value=agent)
        ui._make_role = Mock(side_effect=lambda agent, slug, parent_role_id,
                             description: parent_role_id + '-' + slug)
        problems = ui._create_roles({'dk-new': 'New', 'dk-new-sub': 'Sub'})
        self.assertEqual(problems, [])
        self.assertEqual(
            [c[1]['parent_role_id'] for c in ui._make_role.call_args_list],
            ['dk', 'dk-new'])
        self.assertFalse(agent.add_role_owner.called)
