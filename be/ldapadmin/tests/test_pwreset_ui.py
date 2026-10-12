import unittest
from io import BytesIO
import re
from datetime import datetime, timedelta
from zope.component import getGlobalSiteManager
from zope.sendmail.interfaces import IMailDelivery
from unittest.mock import MagicMock as Mock, patch
from webob import Response
from webob.exc import HTTPNotFound, HTTPSeeOther
from webob.dec import wsgify
from be.ldapadmin import UsersDB
from be.ldapadmin.pwreset_tool import PasswordResetTool, CommonTemplateLogic
from be.ldapadmin.ui_common import TemplateRenderer


def stubbed_renderer():
    renderer = TemplateRenderer(CommonTemplateLogic)
    renderer.wrap = lambda html: "<html>%s</html>" % html
    return renderer


class StubbedPasswordResetTool(PasswordResetTool):
    def __init__(self):
        super(StubbedPasswordResetTool, self).__init__()
        self._render_template = stubbed_renderer()

    def absolute_url(self):
        return "http://test"


def decode_form(request):
    form = {}
    source = request.POST or request.GET
    for name in source:
        value = source[name]
        if name.endswith(':utf8:string'):
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            name = name[:-(len(':utf8:string'))]
        form[name] = value
    return form


class WsgiApp(object):
    def __init__(self, ui):
        self.ui = ui
        self.session = {}

    @wsgify
    def __call__(self, request):
        request.SESSION = self.session
        request.RESPONSE = Mock()
        # z3c.pt reads the content type from the Zope response API
        request.response.getHeader = lambda name, default=None: default
        request.response.setHeader = lambda name, value: None
        request.form = decode_form(request)
        request.get = request.form.get  # Zope request API
        request.AUTHENTICATED_USER = Mock()
        request.AUTHENTICATED_USER.has_permission.return_value = False
        try:
            name = request.path[1:] or 'index_html'
            method = getattr(self.ui, name)
        except AttributeError:
            return HTTPNotFound()
        else:
            self.ui.REQUEST = request
            body = method(request)

            if request.RESPONSE.redirect.called:
                url = request.RESPONSE.redirect.call_args[0][0]
                return HTTPSeeOther(location=url)

            else:
                if isinstance(body, str):
                    return Response(text=body)
                return Response(body)


class Browser(object):
    """ The few mechanize.Browser calls the tests use, over WebOb """

    def __init__(self, app):
        self.app = app
        self.url = None
        self.body = None
        self.form = None

    def _request(self, url, post=None):
        from urllib.parse import urljoin
        from webob import Request
        while True:
            self.url = urljoin(self.url or url, url)
            req = Request.blank(self.url, POST=post)
            resp = req.get_response(self.app)
            if resp.status_int in (301, 302, 303):
                url, post = resp.location, None
                continue
            self.body = resp.body
            return BytesIO(resp.body)

    def open(self, url):
        return self._request(url)

    def select_form(self, name):
        page = parse_html(self.body)
        self.form = page.xpath('//form[@name="%s"]' % name)[0]
        self.fields = dict((i.get('name'), i.get('value') or '')
                           for i in self.form.xpath('.//input[@name]')
                           if i.get('type') != 'submit')

    def __setitem__(self, name, value):
        self.fields[name] = value

    def submit(self):
        return self._request(self.form.get('action') or self.url,
                             post=self.fields)


def parse_email(mimetext):
    from email.parser import Parser
    return Parser().parsestr(mimetext)


def csstext(target, selector):
    from lxml.cssselect import CSSSelector
    return ' '.join(e.text_content() for e in
                    CSSSelector(selector)(target)).strip()


def parse_html(html):
    from lxml.html.soupparser import fromstring
    return fromstring(html)


def extract_link_from_email(email, url_base):
    url_piece = url_base + '/confirm_email?token='
    match = re.search(re.escape(url_piece) + r'(?P<token>\S+)(?=\s)',
                      email.get_payload())
    assert match is not None
    return match.group()


class BrowseTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedPasswordResetTool()
        self.mock_agent = Mock(spec=UsersDB)
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)

        users = [
            {'id': 'teh-user', 'email': 'testpilot@example.com', 'status': ''},
        ]
        filter_users = lambda email: [u for u in users if u['email'] == email]
        self.mock_agent.search_user_by_email.side_effect = filter_users

        self.mail = []
        self.mail_delivery = Mock()
        self.mail_delivery.send = lambda afrom, ato, msg: self.mail.append(msg)

        gsm = getGlobalSiteManager()
        gsm.registerUtility(self.mail_delivery, IMailDelivery, "Mail")

        self.browser = Browser(WsgiApp(self.ui))

    def tearDown(self):
        gsm = getGlobalSiteManager()
        gsm.unregisterUtility(self.mail_delivery, IMailDelivery, "Mail")

    def test_welcome_page(self):
        br = self.browser
        page = parse_html(br.open('http://test/').read())

        self.assertEqual(csstext(page, 'h1'),
                         "Reset Environment Belgium account password")

    def test_enter_email(self):
        br = self.browser
        br.open('http://test/')
        br.select_form(name='identify')
        br['email:utf8:string'] = "testpilot@example.com"
        page = parse_html(br.submit().read())

        self.assertTrue("message has been sent" in csstext(page, 'p'))

        self.assertEqual(len(self.ui._tokens), 1)
        token = list(self.ui._tokens.keys())[0]

        self.assertEqual(len(self.mail), 1)
        email = parse_email(self.mail[0])
        self.assertEqual(email['to'], "testpilot@example.com")
        link = extract_link_from_email(email, 'http://test')
        self.assertEqual(link.rsplit('=', 1)[-1], token)

    def test_enter_bad_email(self):
        br = self.browser
        br.open('http://test/')
        br.select_form(name='identify')
        br['email:utf8:string'] = "badtestpilot@example.com"
        page = parse_html(br.submit().read())

        self.assertEqual(csstext(page, 'div.error-msg'),
                         "Email address not found in database.")
        self.assertEqual(len(self.ui._tokens), 0)
        self.assertEqual(len(self.mail), 0)

    def test_enter_new_password(self):
        token = self.ui._new_token('teh-user')
        link = 'http://test/confirm_email?token=' + token
        br = self.browser
        page = parse_html(br.open(link).read())

        self.assertEqual(csstext(page, 'p tt'), 'teh-user')

        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"
        page = parse_html(br.submit().read())

        self.mock_agent.set_user_password.assert_called_once_with(
            'teh-user', None, "NeWpAsS")
        self.assertTrue("successfully reset" in csstext(page, 'p'))

    def test_new_passwords_do_not_match(self):
        token = self.ui._new_token('teh-user')
        link = 'http://test/confirm_email?token=' + token
        br = self.browser
        br.open(link)
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "blah"
        page = parse_html(br.submit().read())

        self.assertEqual(csstext(page, 'div.error-msg'),
                         "Passwords do not match.")

        # make sure the new form still works
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"
        page = parse_html(br.submit().read())
        self.assertTrue("successfully reset" in csstext(page, 'p'))

    def assert_invalid_token_response(self, page):
        self.assertEqual(csstext(page, 'div.error-msg'),
                         "Password reset link is invalid, perhaps it has "
                         "expired. Please try again.")
        self.assertFalse(self.mock_agent.set_user_password.called)

    def test_invalid_token_in_link(self):
        token = "bogus-token"
        link = 'http://test/confirm_email?token=' + token
        br = self.browser
        page = parse_html(br.open(link).read())

        self.assert_invalid_token_response(page)

    def test_invalid_token_from_form(self):
        token = self.ui._new_token('teh-user')
        link = 'http://test/confirm_email?token=' + token
        br = self.browser
        br.open(link)
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"
        del self.ui._tokens[token]
        page = parse_html(br.submit().read())

        self.assert_invalid_token_response(page)

    @patch('be.ldapadmin.pwreset_tool.datetime')
    def test_token_expiry(self, mock_datetime):
        t0 = datetime(2011, 5, 2, 13, 30, 22)
        mock_datetime.now.return_value = t0
        token = self.ui._new_token('teh-user')
        link = 'http://test/confirm_email?token=' + token

        mock_datetime.now.return_value = t0 + timedelta(days=1, minutes=1)
        br = self.browser
        page = parse_html(br.open(link).read())

        self.assert_invalid_token_response(page)

    @patch('be.ldapadmin.pwreset_tool.datetime')
    def test_token_expiry_in_form(self, mock_datetime):
        t0 = datetime(2011, 5, 2, 13, 30, 22)
        mock_datetime.now.return_value = t0
        token = self.ui._new_token('teh-user')
        link = 'http://test/confirm_email?token=' + token

        br = self.browser
        br.open(link)
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"

        mock_datetime.now.return_value = t0 + timedelta(days=1, minutes=1)
        page = parse_html(br.submit().read())

        self.assert_invalid_token_response(page)

    def test_no_token_reuse(self):
        br = self.browser
        br.open('http://test/')
        br.select_form(name='identify')
        br['email:utf8:string'] = "testpilot@example.com"
        br.submit()
        email = parse_email(self.mail[0])
        link = extract_link_from_email(email, 'http://test')
        token = link.rsplit('=')[-1]

        self.assertTrue(token in self.ui._tokens)

        page = parse_html(br.open(link).read())
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"
        br.submit()

        self.assertFalse(token in self.ui._tokens)

    def test_successful_workflow(self):
        br = self.browser
        br.open('http://test/')
        br.select_form(name='identify')
        br['email:utf8:string'] = "testpilot@example.com"
        br.submit()

        email = parse_email(self.mail[0])
        link = extract_link_from_email(email, 'http://test')
        page = parse_html(br.open(link).read())
        br.select_form(name='new-password')
        br['password:utf8:string'] = "NeWpAsS"
        br['password-confirm:utf8:string'] = "NeWpAsS"
        page = parse_html(br.submit().read())

        self.mock_agent.set_user_password.assert_called_once_with(
            'teh-user', None, "NeWpAsS")
        self.assertTrue("successfully reset" in csstext(page, 'p'))

    @patch('be.ldapadmin.ui_common.NETWORK_NAME', 'SINAnet')
    def test_network_name_customization(self):
        br = self.browser
        page = parse_html(br.open('http://test/').read())

        self.assertEqual(csstext(page, 'h1'), "Reset SINAnet account password")
