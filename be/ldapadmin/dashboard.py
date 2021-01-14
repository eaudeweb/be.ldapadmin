import operator
import os

from App.config import getConfiguration
from AccessControl import ClassSecurityInfo, getSecurityManager
from AccessControl.Permissions import view
from OFS.Folder import Folder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from be.ldapadmin.ui_common import TemplateRenderer, CommonTemplateLogic
from be.ldapadmin.constants import NETWORK_URL

KNOWN_TYPES = {
    'LDAP Roles Editor': {
        'description': ('Browse Roles and Roles\' Members in LDAP'
                        '<br /><i>[system administration]</i>')
    },
    'LDAP Organisations Editor': {
        'description': ('Browse organisations'
                        '<br /><i>[system administration]</i>')
    },
    'LDAP Password Reset Tool': {
        'description': ('Reset account password'
                        '<br /><i>[available to any user]</i>')
    },
    'LDAP Users Admin': {
        'description': ('Manage User Accounts'
                        '<br /><i>[system administration]</i>')
    },
    'LDAP Users Editor': {
        'description': ('Manage your profile information'
                        '<br /><i>[available to any user]</i>')
    },
    'My Profile Overview': {
        'description': ('Overview on my memberships in interest groups,'
                        ' Roles and Subscriptions'
                        '<br /><i>[available to any user]</i>')
    },
    'LDAP User Details': {
        'description': ('LDAP User page (User Directory)'
                        '<br /><i>[available to any user]</i>')
    }
}

SESSION_PREFIX = 'be.ldapadmin.dashboard'
SESSION_MESSAGES = SESSION_PREFIX + '.messages'
SESSION_FORM_DATA = SESSION_PREFIX + '.form_data'
SESSION_FORM_ERRORS = SESSION_PREFIX + '.form_errors'

# Permission
ldap_access_ldap_explorer = 'LDAP access LDAP explorer'

CONFIG = getConfiguration()
CONFIG.environment.update(os.environ)

manage_add_ldap_admin_html = PageTemplateFile('zpt/ldapadmin_manage_add',
                                              globals())


class FakeTool(object):
    """
    Some tools we want to include in LDAP Explorer are not objects in
    database. Fake/mock them to use the same pattern in logic and
    templates.

    """

    def __init__(self, meta_type, title, icon, absolute_url):
        self.meta_type = meta_type
        self.title = title
        self.icon = icon
        self.absolute_url = absolute_url


FAKES = [
    ('My Profile Overview', 'My Profile Overview',
     '++resource++be.ldapadmin-www/profile_overview.png',
     NETWORK_URL + '/profile_overview')
]


def manage_add_ldap_admin(parent, id, REQUEST=None):
    """ Create a new Dashboard object """
    if REQUEST is not None:
        form = REQUEST.form
    else:
        form = {}
    obj = Dashboard()
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


class Dashboard(Folder):
    """
    The ldapadmin dashboard acts as container for the ldapadmin tools
    (organisation editor, users admin, roles editor, etc.).
    The tools should be created inside the dashboard folder so they can be
    rendered and linked in the dashboard template (some style will be applied
    in connection with their meta type)

    """

    meta_type = 'LDAP Explorer'
    icon = '++resource++be.ldapadmin-www/ldap_dashboard.gif'
    security = ClassSecurityInfo()
    session_messages = SESSION_MESSAGES

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def checkDashboardPermission(self):
        return getSecurityManager().checkPermission(
            ldap_access_ldap_explorer, self)

    security.declareProtected(view, 'get_slug')

    def get_slug(self, tool):
        """
        Returns a given slug for the `tool`, based on meta type,
        useful for referencing static files

        """
        return tool.meta_type.lower().replace(' ', '_')

    def get_tool_info(self, tool):
        """
        Returns meta properties of this tool as defined at the top of this
        module

        """
        return KNOWN_TYPES[tool.meta_type]

    security.declareProtected(view, 'index_html')

    def index_html(self, REQUEST):
        """ Dashboard page """
        tools = self.objectValues(KNOWN_TYPES.keys())
        for fake in FAKES:
            tools.append(FakeTool(*fake))
        tools.sort(key=operator.attrgetter('title'))
        return self._render_template("zpt/dashboard.zpt", **{'tools': tools})
