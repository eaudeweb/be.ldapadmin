''' users admin and user details pages '''
import unittest
from unittest.mock import MagicMock as Mock, patch

from lxml.html.soupparser import fromstring

from be.ldapadmin.constants import USER_INFO_KEYS
from be.ldapadmin.ui_common import TemplateRenderer, extend_crumbs
from be.ldapadmin.userdetails import UserDetails
from be.ldapadmin.users_admin import UsersAdmin, CommonTemplateLogic


def stubbed_renderer():
    renderer = TemplateRenderer(CommonTemplateLogic)
    renderer.wrap = lambda html: "<html>%s</html>" % html
    renderer.browserview = lambda context, name: lambda *args: ''
    return renderer


def mock_request(form):
    request = Mock()
    request.SESSION = {}
    request.form = form
    return request


def user_fixture(**kw):
    user = dict((key, '') for key in USER_INFO_KEYS)
    user.update(id='anne', uid='anne', first_name='Anne', last_name='Tester',
                full_name='Anne Tester', email='anne@example.com', orgs=[],
                membership_type={})
    user.update(kw)
    return user


class StubbedUsersAdmin(UsersAdmin):
    def __init__(self):
        super().__init__()
        self._render_template = stubbed_renderer()

    def absolute_url(self):
        return "URL"

    def checkPermissionEditUsers(self):
        return True

    def can_edit_users(self):
        return True


class UsersAdminTest(unittest.TestCase):

    def setUp(self):
        self.ui = StubbedUsersAdmin()
        self.agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.agent)

    def test_search_results(self):
        self.agent.search_user.return_value = [user_fixture()]
        request = mock_request({'name': 'anne', 'lookup': 'all'})
        self.ui.REQUEST = request
        page = fromstring(self.ui.index_html(request))
        self.assertIn('Anne Tester', page.text_content())

    def test_edit_user_form(self):
        self.agent.user_info.return_value = user_fixture()
        self.agent.all_organisations.return_value = {
            'dk_org': {'name': 'Org', 'name_native': ''}}
        request = mock_request({'id': 'anne'})
        self.ui.REQUEST = request
        page = fromstring(self.ui.edit_user(request))
        first_name = page.xpath('//input[@name="first_name:utf8:string"]')
        self.assertEqual(first_name[0].get('value'), 'Anne')


class StubbedUserDetails(UserDetails):
    def __init__(self):
        self._render_template = stubbed_renderer()

    def absolute_url(self):
        return "URL"


class UserDetailsTest(unittest.TestCase):

    @patch('be.ldapadmin.userdetails.logged_in_user', Mock(return_value='anne'))
    @patch('be.ldapadmin.userdetails._is_authenticated', Mock(return_value=True))
    def test_roles_listed(self):
        ui = StubbedUserDetails()
        agent = Mock()
        ui._get_ldap_agent = Mock(return_value=agent)
        agent.member_roles_info.return_value = [
            ('places-bank', {'description': [b'Bank']}),
            ('places-shiny', {'description': [b'Shiny']}),
        ]
        agent.user_info.return_value = user_fixture()
        agent.get_profile_picture.return_value = None
        agent.get_certificate.return_value = None
        agent._get_metadata.return_value = []
        request = mock_request({'uid': 'anne'})
        ui.REQUEST = request
        page = fromstring(ui.index_html(request))
        self.assertIn('places-bank', page.text_content())
        self.assertIn('places-shiny', page.text_content())


class BreadcrumbsTest(unittest.TestCase):

    def test_extend_crumbs_returns_text(self):
        html = ('<div class="breadcrumbtrail">'
                '<div class="breadcrumbitem"><a href="/">Home</a></div>'
                '<div class="breadcrumbitemlast">Roles</div></div>')
        out = extend_crumbs(html, 'URL', [('Bank', 'URL/?role_id=bank')])
        self.assertIsInstance(out, str)
        self.assertIn('<a href="URL">Roles</a>', out)
        self.assertIn('breadcrumbitemlast', out)
