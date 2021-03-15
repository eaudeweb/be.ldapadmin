''' module related to displaying user details '''

import json
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from zope.component import getMultiAdapter, getUtility
from zope.component.interfaces import ComponentLookupError
from zope.sendmail.interfaces import IMailDelivery
from AccessControl import ClassSecurityInfo  # , Unauthorized
from AccessControl.Permissions import view, view_management_screens
from AccessControl.unauthorized import Unauthorized
from DateTime import DateTime
from image_processor import scale_to
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from persistent.mapping import PersistentMapping
from zExceptions import NotFound
from ldap import CONSTRAINT_VIOLATION, NO_SUCH_OBJECT, SCOPE_BASE
from be.ldapadmin.constants import NETWORK_NAME, MAIL_ADDRESS_FROM
from be.ldapadmin import ldap_config
from be.ldapadmin.logic_common import _is_authenticated, logged_in_user
from be.ldapadmin.logic_common import load_template, split_to_list
from be.ldapadmin.ui_common import TemplateRenderer, CommonTemplateLogic

ldap_edit_users = 'LDAP edit users'

log = logging.getLogger(__name__)

manage_add_userdetails_html = PageTemplateFile(
    'zpt/userdetails/user_manage_add', globals())
manage_add_userdetails_html.ldap_config_edit_macro = ldap_config.edit_macro
manage_add_userdetails_html.config_defaults = lambda: ldap_config.defaults

WIDTH = 128
HEIGHT = 192


def manage_add_userdetails(parent, id, REQUEST=None):
    """ Create a new UserDetails object """
    form = (REQUEST.form if REQUEST is not None else {})
    config = ldap_config.read_form(form)
    obj = UserDetails(config)
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())


SESSION_MESSAGES = 'be.ldapadmin.messages'


def _get_session_messages(request):
    session = request.SESSION
    if SESSION_MESSAGES in session.keys():
        msgs = dict(session[SESSION_MESSAGES])
        del session[SESSION_MESSAGES]
    else:
        msgs = {}
    return msgs


def _set_session_message(request, msg_type, msg):
    session = request.SESSION
    if SESSION_MESSAGES not in session.keys():
        session[SESSION_MESSAGES] = PersistentMapping()
    # TODO: allow for more than one message of each type
    session[SESSION_MESSAGES][msg_type] = msg


class UserDetails(SimpleItem):
    meta_type = 'LDAP User Details'
    security = ClassSecurityInfo()
    icon = '++resource++be.ldapadmin-www/users_editor.gif'

    _render_template = TemplateRenderer(CommonTemplateLogic)

    manage_options = (
        {'label': 'Configure', 'action': 'manage_edit'},
        {'label': 'View', 'action': ''},
    ) + PropertyManager.manage_options + SimpleItem.manage_options

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/userdetails/user_manage_edit',
                                   globals())
    manage_edit.ldap_config_edit_macro = ldap_config.edit_macro

    security.declareProtected(view_management_screens, 'get_config')

    def get_config(self):
        config = dict(getattr(self, '_config', {}))
        return config

    security.declareProtected(view_management_screens, 'manage_edit_save')

    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self._config.update(ldap_config.read_form(REQUEST.form, edit=True))
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def __init__(self, config={}):
        super(UserDetails, self).__init__()
        self._config = PersistentMapping(config)

    def _get_ldap_agent(self, bind=True, secondary=False):
        return ldap_config._get_ldap_agent(self, bind, secondary)

    def _prepare_user_page(self, uid):
        """Shared by index_html and simple_profile"""
        is_auth = _is_authenticated(self.REQUEST)
        agent = self._get_ldap_agent(bind=is_auth)
        ldap_roles = sorted(agent.member_roles_info('user',
                                                    uid,
                                                    ('description',)))
        roles = []
        orgs = []
        for (role_id, attrs) in ldap_roles:
            roles.append((role_id,
                          attrs.get('description', ('', ))[0].decode('utf8')))
        user = agent.user_info(uid)
        user['email'] = split_to_list(user['email'])
        user['jpegPhoto'] = agent.get_profile_picture(uid)
        user['certificate'] = agent.get_certificate(uid)
        # user['organisation'] is a CSV string with what the user has in the
        # `o` property, while user['orgs'] is a list of orgasations that have
        # current user as member. Both shuld in theory be the same, but
        # some users still have older orgs, from the free text field period.
        user_orgs = user['organisation']
        if user_orgs:
            user_orgs = split_to_list(user_orgs)
        else:
            user_orgs = []
        orgs_with_user = user['orgs']

        for org in set(user_orgs).union(set(orgs_with_user)):
            org_info = agent.org_info(org)
            org_id = org_info.get('id')
            if 'INVALID' in org_id or 'INEXISTENT' in org_id:
                orgs.append((org, ''))
            else:
                name = org_info['name'].strip() or org_id.title().replace(
                    '_', ' ')
                orgs.append((org_id, name))
        pwdChangedTime = user['pwdChangedTime']
        if pwdChangedTime:
            pwdChangedTime = datetime.strptime(pwdChangedTime, '%Y%m%d%H%M%SZ')
            user['pwdChanged'] = pwdChangedTime.strftime('%Y-%m-%d %H:%M:%S')
            user['pwdExpired'] = datetime.now() - timedelta(
                days=365) > pwdChangedTime
        else:
            user['pwdChanged'] = ''
            user['pwdExpired'] = True
        return user, roles, orgs

    security.declarePublic("index_html")

    def index_html(self, REQUEST):
        """ """
        is_auth = _is_authenticated(REQUEST)
        uid = REQUEST.form.get('uid')
        if not uid and is_auth:
            uid = logged_in_user(REQUEST)
        if not uid:
            # a missing uid while unauthenticated can only mean this page
            # is called by accident
            return
        date_for_roles = REQUEST.form.get('date_for_roles')

        if "," in uid:
            user = None
            roles = None
            multi = json.dumps({'users': uid.split(",")})
        else:
            multi = None
            user, roles, orgs = self._prepare_user_page(uid)

        # we can only connect to ldap with bind=True if we have an
        # authenticated user
        agent = self._get_ldap_agent(bind=is_auth)

        user_dn = agent._user_dn(uid)
        log_entries = list(reversed(agent._get_metadata(user_dn)))
        VIEWS = {}
        filtered_roles = set([info[0] for info in roles])   # + owner_roles)
        if date_for_roles:
            filter_date = DateTime(date_for_roles).asdatetime().date()
        else:
            filter_date = DateTime().asdatetime().date()

        for entry in log_entries:
            date = DateTime(entry['timestamp']).toZone("CET")
            entry['timestamp'] = date.ISO()
            view = VIEWS.get(entry['action'])
            if not view:
                view = getMultiAdapter((self, self.REQUEST),
                                       name="details_" + entry['action'])
                VIEWS[entry['action']] = view
            entry['view'] = view

            _roles = entry.get('data', {}).get('roles')
            _role = entry.get('data', {}).get('role')
            if date.asdatetime().date() >= filter_date:
                if entry['action'] == 'ENABLE_ACCOUNT':
                    filtered_roles.difference_update(set(_roles))
                elif entry['action'] == "DISABLE_ACCOUNT":
                    filtered_roles.update(set(_roles))
                elif entry['action'] in ["ADDED_TO_ROLE"]:
                    if _role and _role in filtered_roles:
                        filtered_roles.remove(_role)
                elif entry['action'] in ["REMOVED_FROM_ROLE"]:
                    if _role:
                        filtered_roles.add(_role)

        output = []
        for entry in log_entries:
            if output:
                last_entry = output[-1]
                check = ['author', 'action']
                flag = True
                for k in check:
                    if last_entry[k] != entry[k]:
                        flag = False
                        break
                if flag:
                    last_entry['data'].append(entry['data'])
                else:
                    entry['data'] = [entry['data']]
                    output.append(entry)
            else:
                entry['data'] = [entry['data']]
                output.append(entry)

        removed_roles = []
        if user.get('status') == 'disabled':
            auth_user = self.REQUEST.AUTHENTICATED_USER
            if not bool(auth_user.has_permission(ldap_edit_users, self)):
                raise NotFound("User '%s' does not exist" % uid)
            # process log entries to list the roles the user had before
            # being disabled
            for entry in log_entries:
                if entry['action'] == 'DISABLE_ACCOUNT':
                    for role in entry['data'][0]['roles']:
                        try:
                            role_description = agent.role_info(role)[
                                'description']
                        except Exception:
                            role_description = ("This role doesn't exist "
                                                "anymore")
                        removed_roles.append((role, role_description))
                    break

        return self._render_template(
            "zpt/userdetails/index.zpt", context=self,
            filtered_roles=filtered_roles, user=user, roles=roles, orgs=orgs,
            removed_roles=removed_roles, multi=multi, log_entries=output)

    security.declarePublic("simple_profile")

    def simple_profile(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        user, roles, orgs = self._prepare_user_page(uid)
        tr = TemplateRenderer(CommonTemplateLogic)
        return tr.__of__(self).render("zpt/userdetails/simple.zpt",
                                      user=user, roles=roles, orgs=orgs)

    security.declarePublic("userphoto_jpeg")

    def userphoto_jpeg(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        agent = self._get_ldap_agent()
        REQUEST.RESPONSE.setHeader('Content-Type', 'image/jpeg')
        return agent.get_profile_picture(uid)

    security.declarePublic("usercertificate")

    def usercertificate(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        agent = self._get_ldap_agent()
        REQUEST.RESPONSE.setHeader('Content-Type', 'application/pkix-cert')
        return agent.get_certificate(uid)

    security.declarePublic("get_user_orgs")

    def get_user_orgs(self, user_id=None):
        """ Convenience method to be used in the /directory/ folder
        """
        if user_id is None:
            user_id = self.REQUEST.form.get('uid')

        agent = self._get_ldap_agent()
        return agent.orgs_for_user(user_id)

    security.declareProtected(view, 'can_edit_users')

    def can_edit_users(self):
        user = self.REQUEST.AUTHENTICATED_USER
        return bool(user.has_permission(ldap_edit_users, self))

    security.declareProtected(view, 'change_password_html')

    def change_password_html(self, REQUEST):
        """ view """
        if not _is_authenticated(REQUEST):
            raise Unauthorized

        return self._render_template('zpt/change_password.zpt',
                                     user_id=logged_in_user(REQUEST),
                                     base_url=self.absolute_url(),
                                     **_get_session_messages(REQUEST))

    security.declareProtected(view, 'change_password')

    def change_password(self, REQUEST):
        """ view """
        form = REQUEST.form
        user_id = logged_in_user(REQUEST)
        agent = self._get_ldap_agent(bind=True)
        user_info = agent.user_info(user_id)

        if form['new_password'] != form['new_password_confirm']:
            _set_session_message(REQUEST, 'error',
                                 "New passwords do not match")
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/change_password_html')

        try:
            agent.set_user_password(user_id, form['old_password'],
                                    form['new_password'])

            options = {
                'first_name': user_info['first_name'],
                'password': form['new_password'],
                'network_name': NETWORK_NAME,
            }

            email_template = load_template('zpt/email_change_password.zpt')
            email_password_body = email_template.pt_render(options)
            addr_to = user_info['email']

            message = MIMEText(email_password_body)
            message['From'] = MAIL_ADDRESS_FROM
            message['To'] = addr_to
            message['Subject'] = "%s Account - New password" % NETWORK_NAME

            try:
                mailer = getUtility(IMailDelivery, name="Mail")
                mailer.send(MAIL_ADDRESS_FROM, split_to_list(addr_to),
                            message.as_string())
            except ComponentLookupError:
                mailer = getUtility(IMailDelivery, name="naaya-mail-delivery")
                mailer.send(MAIL_ADDRESS_FROM, split_to_list(addr_to), message)

        except ValueError:
            _set_session_message(REQUEST, 'error', "Old password is wrong")
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/change_password_html')
        except CONSTRAINT_VIOLATION as e:
            if e.message['info'] in [
                    'Password fails quality checking policy']:
                try:
                    defaultppolicy = agent.conn.search_s(
                        'cn=defaultppolicy,ou=pwpolicies,o=EIONET,'
                        'l=Europe',
                        SCOPE_BASE)
                    p_length = defaultppolicy[0][1]['pwdMinLength'][0]
                    message = '%s (min. %s characters)' % (
                        e.message['info'], p_length)
                except NO_SUCH_OBJECT:
                    message = e.message['info']
            else:
                message = e.message['info']
            _set_session_message(REQUEST, 'error', message)
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/change_password_html')

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/password_changed_html')

    security.declareProtected(view, 'password_changed_html')

    def password_changed_html(self, REQUEST):
        """ view """
        options = {
            'messages': [
                "Password changed successfully. You must log in again."],
            'base_url': self.absolute_url(),
        }
        return self._render_template('zpt/result_page.zpt', **options)

    security.declareProtected(view, 'profile_picture_html')

    def profile_picture_html(self, REQUEST):
        """ view """
        if not _is_authenticated(REQUEST):
            raise Unauthorized
        user_id = logged_in_user(REQUEST)
        agent = self._get_ldap_agent(bind=True)

        if agent.get_profile_picture(user_id):
            has_image = True
        else:
            has_image = False
        return self._render_template('zpt/profile_picture.zpt',
                                     user_id=logged_in_user(REQUEST),
                                     base_url=self.absolute_url(),
                                     has_current_image=has_image,
                                     here=self,
                                     **_get_session_messages(REQUEST))

    security.declareProtected(view, 'profile_picture')

    def profile_picture(self, REQUEST):
        """ view """
        if not _is_authenticated(REQUEST):
            raise Unauthorized
        image_file = REQUEST.form.get('image_file', None)
        if image_file:
            picture_data = image_file.read()
            user_id = logged_in_user(REQUEST)
            agent = self._get_ldap_agent(bind=True)
            try:
                color = (255, 255, 255)
                picture_data = scale_to(picture_data, WIDTH, HEIGHT, color)
                success = agent.set_user_picture(user_id, picture_data)
            except ValueError:
                _set_session_message(REQUEST, 'error',
                                     "Error updating picture")
                return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                                 '/profile_picture_html')
            if success:
                success_text = "That's a beautiful picture."
                _set_session_message(REQUEST, 'message', success_text)
            else:
                _set_session_message(REQUEST, 'error',
                                     "Error updating picture.")
        else:
            _set_session_message(REQUEST, 'error',
                                 "You must provide a JPG file.")
        return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                         '/profile_picture_html')

    security.declareProtected(view, 'profile_picture_jpg')

    def profile_picture_jpg(self, REQUEST):
        """
        Returns jpeg picture data for logged-in user.
        Assumes picture is available in LDAP.

        """
        user_id = logged_in_user(REQUEST)
        agent = self._get_ldap_agent(bind=True)
        photo = agent.get_profile_picture(user_id)
        REQUEST.RESPONSE.setHeader('Content-Type', 'image/jpeg')
        return photo

    security.declareProtected(view, 'remove_picture')

    def remove_picture(self, REQUEST):
        """ Removes existing profile picture for loggedin user """
        user_id = logged_in_user(REQUEST)
        agent = self._get_ldap_agent(bind=True)
        try:
            agent.set_user_picture(user_id, None)
        except Exception:
            _set_session_message(REQUEST, 'error', "Something went wrong.")
        else:
            _set_session_message(REQUEST, 'message', "No image for you.")
        return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                         '/profile_picture_html')
