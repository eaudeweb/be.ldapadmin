''' organisations editor '''
# pylint: disable=too-many-lines

import codecs
from datetime import datetime
import itertools
import logging
import operator
import os
import re
from StringIO import StringIO
from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError
from zope.sendmail.interfaces import IMailDelivery
from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view, view_management_screens
from AccessControl.unauthorized import Unauthorized
from App.class_init import InitializeClass
from App.config import getConfiguration
import deform
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.PropertyManager import PropertyManager
from OFS.SimpleItem import SimpleItem
from ldap import NO_SUCH_OBJECT
from ldap import INVALID_DN_SYNTAX
from be.ldapadmin.logic_common import _create_plain_message
from persistent.mapping import PersistentMapping
import ldap
import ldap_config
import xlwt
from be.ldapadmin.db_agent import UserNotFound, NameAlreadyExists
from be.ldapadmin.db_agent import OrgRenameError, editable_org_fields
from be.ldapadmin.constants import NETWORK_NAME, USER_INFO_KEYS
from be.ldapadmin.countries import get_country, get_country_options
from be.ldapadmin.ui_common import extend_crumbs, CommonTemplateLogic
from be.ldapadmin.ui_common import SessionMessages
from be.ldapadmin.ui_common import TemplateRenderer
from be.ldapadmin.logic_common import _is_authenticated, logged_in_user
from be.ldapadmin.logic_common import load_template
from be.ldapadmin.schema import user_info_schema


cfg = getConfiguration()
cfg.environment.update(os.environ)

ADDR_FROM = getattr(cfg, 'environment', {}).get(
    'ADDR_FROM', 'no-reply@envcoord.health.fgov.be')

log = logging.getLogger('orgs_editor')

ldap_edit_orgs = 'LDAP edit organisations'
ldap_edit_users = 'LDAP edit users'

manage_add_orgs_editor_html = PageTemplateFile('zpt/orgs_manage_add',
                                               globals())
manage_add_orgs_editor_html.ldap_config_edit_macro = ldap_config.edit_macro
manage_add_orgs_editor_html.config_defaults = lambda: ldap_config.defaults


def manage_add_orgs_editor(parent, id, REQUEST=None):
    """ Adds a new Organisations Editor object """
    form = (REQUEST.form if REQUEST is not None else {})
    config = ldap_config.read_form(form)
    obj = OrganisationsEditor(config)
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


def get_template_macro(name):
    return load_template('zpt/orgs_macros.zpt').macros[name]


SESSION_PREFIX = 'be.ldapadmin.orgs_editor'
SESSION_MESSAGES = SESSION_PREFIX + '.messages'
SESSION_FORM_DATA = SESSION_PREFIX + '.form_data'
SESSION_FORM_ERRORS = SESSION_PREFIX + '.form_errors'

user_info_edit_schema = user_info_schema.clone()
user_info_edit_schema['postal_address'].widget = deform.widget.TextAreaWidget()
del user_info_edit_schema['first_name']
del user_info_edit_schema['last_name']


def _set_session_message(request, msg_type, msg):
    SessionMessages(request, SESSION_MESSAGES).add(msg_type, msg)


class OrganisationsEditor(SimpleItem, PropertyManager):
    meta_type = 'LDAP Organisations Editor'
    security = ClassSecurityInfo()
    icon = '++resource++be.ldapadmin-www/eionet_organisations_editor.gif'
    session_messages = SESSION_MESSAGES
    manage_options = (
        {'label': 'Configure', 'action': 'manage_edit'},
        {'label': 'View', 'action': ''},
    ) + PropertyManager.manage_options + SimpleItem.manage_options

    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w', 'label': 'Title'},
    )

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def _set_breadcrumbs(self, stack):
        self.REQUEST._orgs_editor = stack

    def breadcrumbtrail(self):
        crumbs_html = self.aq_parent.breadcrumbtrail(self.REQUEST)
        extra_crumbs = getattr(self.REQUEST, '_orgs_editor', [])
        return extend_crumbs(crumbs_html, self.absolute_url(), extra_crumbs)

    def __init__(self, config={}):
        super(OrganisationsEditor, self).__init__()
        self._config = PersistentMapping(config)

    security.declareProtected(view_management_screens, 'get_config')

    def get_config(self):
        return dict(self._config)

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/orgs_manage_edit', globals())
    manage_edit.ldap_config_edit_macro = ldap_config.edit_macro

    security.declarePublic('checkPermissionView()')

    def checkPermissionView(self):
        user = self.REQUEST.AUTHENTICATED_USER
        return bool(user.has_permission(view, self))

    security.declarePublic('checkPermissionEditOrganisations')

    def checkPermissionEditOrganisations(self):
        user = self.REQUEST.AUTHENTICATED_USER
        return bool(user.has_permission(ldap_edit_orgs, self))

    security.declareProtected(view_management_screens, 'manage_edit_save')

    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self._config.update(ldap_config.read_form(REQUEST.form, edit=True))
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def _get_ldap_agent(self, bind=True, secondary=False):
        return ldap_config._get_ldap_agent(self, bind, secondary)

    security.declareProtected(view, 'index_html')

    def index_html(self, REQUEST):
        """ Index of organisations """
        country = REQUEST.get('country')
        agent = self._get_ldap_agent(secondary=True)
        orgs_by_id = agent.all_organisations()
        countries = dict(get_country_options(country=country))
        orgs = []
        for org_id, info in orgs_by_id.iteritems():
            country = countries.get(info['country'])
            if country:
                orgs.append({'id': org_id,
                             'name': info['name'] or org_id.title().replace(
                                 '_', ' '),
                             'country': country['name'],
                             'country_pub_code': country['pub_code']})
        orgs.sort(key=operator.itemgetter('id'))
        options = {
            'sorted_organisations': orgs,
        }
        return self._render_template('zpt/orgs_index.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'export_organisations')

    def export_organisations(self, REQUEST):
        """ Export of organisations """

        agent = self._get_ldap_agent()
        orgs_by_id = agent.all_organisations()

        countries = dict(get_country_options())
        country = 'all'

        orgs = []
        for org_id, info in orgs_by_id.iteritems():
            country = countries.get(info['country'])
            if country:
                orgs.append({'id': org_id,
                             'name': info['name'],
                             'country': country['name'],
                             'country_pub_code': country['pub_code']})
        orgs.sort(key=operator.itemgetter('id'))

        for d in orgs:
            org_info = agent.org_info(d['id'])
            d.update(org_info)

        wb = xlwt.Workbook()
        org_sheet = wb.add_sheet("Organisations")
        users_sheet = wb.add_sheet("Members")

        style_header = xlwt.XFStyle()
        style_org_header = xlwt.XFStyle()
        style_normal = xlwt.XFStyle()

        normalfont = xlwt.Font()
        headerfont = xlwt.Font()
        headerfont.bold = True
        biggerheaderfont = xlwt.Font()
        biggerheaderfont.bold = True
        biggerheaderfont.height = int(biggerheaderfont.height * 1.3)

        style_header.font = headerfont
        style_normal.font = normalfont
        style_org_header.font = biggerheaderfont

        cols = [
            'id',
            'name',
            'locality',
            'postal_address',
            'fax',
            'email',
        ]
        for i, col in enumerate(cols):
            org_sheet.write(0, i, col.capitalize(), style_header)

        org_sheet.write(0, 6, "Members count", style_header)

        for i, row in enumerate(orgs):
            org_sheet.write(i + 2, 0, row['id'], style_normal)
            org_sheet.write(i + 2, 1, row['name'], style_normal)
            org_sheet.write(i + 2, 2, row['locality'], style_normal)
            org_sheet.write(i + 2, 3, row['postal_address'], style_normal)
            org_sheet.write(i + 2, 4, row['fax'], style_normal)
            org_sheet.write(i + 2, 5, row['email'], style_normal)
            members = agent.members_in_org(row['id'])   # TODO: optimize
            org_sheet.write(i + 2, 6, len(members), style_normal)

        org_sheet.col(1).set_width(9000)
        org_sheet.col(2).set_width(5000)
        org_sheet.col(3).set_width(9000)
        org_sheet.col(4).set_width(4000)
        org_sheet.col(5).set_width(5000)

        row_counter = 0
        for org in orgs:
            org_id, org_name = org['id'], org['name']

            users_sheet.write(row_counter, 0, org_name, style_org_header)
            row = users_sheet.row(row_counter)
            row.height = int(row.height * 1.3)
            row_counter += 2

            org_members = []

            members = agent.members_in_org(org_id)
            for user_id in members:
                try:
                    org_members.append(agent.user_info(user_id))
                except (NO_SUCH_OBJECT, UserNotFound):
                    pass
            org_members.sort(key=operator.itemgetter('first_name'))

            cols = [
                'user id',
                'fullname',
                'email',
            ]

            for i, col in enumerate(cols):
                users_sheet.write(row_counter, i, col, style_header)

            for i, member in enumerate(org_members, 1):
                users_sheet.write(row_counter + i, 0, member['uid'])
                users_sheet.write(row_counter + i, 1, member['full_name'])
                users_sheet.write(row_counter + i, 2, member['email'])

            users_sheet.col(0).set_width(4000)
            users_sheet.col(1).set_width(6000)
            users_sheet.col(2).set_width(9000)

            row_counter += i + 2

        out = StringIO()
        wb.save(out)
        out.seek(0)
        out = out.read()

        RESPONSE = REQUEST.RESPONSE

        RESPONSE.setHeader('Content-Type', "application/vnd.ms-excel")
        RESPONSE.setHeader('Content-Length', len(out))
        RESPONSE.setHeader('Pragma', 'public')
        RESPONSE.setHeader('Cache-Control', 'max-age=0')
        RESPONSE.addHeader("content-disposition",
                           "attachment; filename=%s-organisations.xls" %
                           country)

        return out

    def export_org(self, REQUEST):
        """ Export of one organisation """
        if not _is_authenticated(REQUEST):
            raise Unauthorized

        org_id = REQUEST.form['id']

        agent = self._get_ldap_agent()
        org_info = agent.org_info(org_id)
        wb = xlwt.Workbook()
        org_sheet = wb.add_sheet("Organisation Details")
        users_sheet = wb.add_sheet("Users")

        style_header = xlwt.XFStyle()
        style_normal = xlwt.XFStyle()
        normalfont = xlwt.Font()
        headerfont = xlwt.Font()
        headerfont.bold = True
        style_header.font = headerfont
        style_normal.font = normalfont

        cols = [
            'id',
            'name',
            'locality',
            'postal_address',
            'fax',
            'email',
        ]
        for i, col in enumerate(cols):
            org_sheet.write(0, i, col, style_header)
            org_sheet.write(2, i, org_info[col], style_normal)

        org_sheet.col(1).set_width(9000)
        org_sheet.col(2).set_width(5000)
        org_sheet.col(3).set_width(9000)
        org_sheet.col(4).set_width(4000)
        org_sheet.col(5).set_width(5000)

        org_members = []
        members = agent.members_in_org(org_id)

        for user_id in members:
            try:
                org_members.append(agent.user_info(user_id))
            except (NO_SUCH_OBJECT, UserNotFound):
                pass

        org_members.sort(key=operator.itemgetter('first_name'))

        cols = [
            'user id',
            'fullname',
            'email',
        ]
        for i, col in enumerate(cols):
            users_sheet.write(0, i, col, style_header)

        for i, member in enumerate(org_members, 2):
            users_sheet.write(i, 0, member['uid'])
            users_sheet.write(i, 1, member['full_name'])
            users_sheet.write(i, 2, member['email'])

        users_sheet.col(0).set_width(4000)
        users_sheet.col(1).set_width(6000)
        users_sheet.col(2).set_width(9000)

        out = StringIO()
        wb.save(out)
        out.seek(0)
        out = out.read()

        RESPONSE = REQUEST.RESPONSE

        RESPONSE.setHeader('Content-Type', "application/vnd.ms-excel")
        RESPONSE.setHeader('Content-Length', len(out))
        RESPONSE.setHeader('Pragma', 'public')
        RESPONSE.setHeader('Cache-Control', 'max-age=0')
        RESPONSE.addHeader("content-disposition",
                           "attachment; filename=%s.xls" % org_id)

        return out

    security.declareProtected(view, 'organisation')

    def organisation(self, REQUEST):
        """ Index of an organisation """
        org_id = REQUEST.form.get('id')
        if not org_id:
            return REQUEST.RESPONSE.redirect(self.absolute_url())
        agent = self._get_ldap_agent()
        org_info = agent.org_info(org_id)
        if not org_info['name']:
            org_info['name'] = org_id.title().replace('_', ' ')
        options = {
            'organisation': org_info,
            # 'country': get_country(org_info['country'])['name'],
        }
        self._set_breadcrumbs([('%s Organisation' % org_id, '#')])
        return self._render_template('zpt/orgs_view.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'create_organisation_html')

    def create_organisation_html(self, REQUEST):
        """ Page for adding an organisation """
        countries = get_country_options()
        options = {
            'countries': countries,
            'form_macro': get_template_macro('org_form_fields'),
            'create_mode': True,
        }

        session = REQUEST.SESSION
        if SESSION_FORM_DATA in session.keys():
            options['org_info'] = session[SESSION_FORM_DATA]
            del session[SESSION_FORM_DATA]
        else:
            options['org_info'] = {}

        self._set_breadcrumbs([('Create Organisation', '#')])
        return self._render_template('zpt/orgs_create.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'create_organisation')

    def create_organisation(self, REQUEST):
        """ Create organisation """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)

        errors = validate_org_info(org_id, org_info, create_mode=True)
        if errors:
            msg = "Organisation not created. Please correct the errors below."
            _set_session_message(REQUEST, 'error', msg)
            for msg in itertools.chain(*errors.values()):
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.SESSION[SESSION_FORM_DATA] = dict(org_info, id=org_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/create_organisation_html')
            return

        org_id = str(org_id)
        agent = self._get_ldap_agent(bind=True)
        try:
            with agent.new_action():
                agent.create_org(org_id, org_info)
        except ldap.ALREADY_EXISTS:
            msg = "Organisation not created. Please correct the errors below."
            _set_session_message(REQUEST, 'error', msg)
            _set_session_message(
                REQUEST, 'error', 'Organisation ID exists already')
            REQUEST.SESSION[SESSION_FORM_DATA] = dict(org_info, id=org_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/create_organisation_html')
            return

        msg = 'Organisation "%s" created successfully.' % org_id
        _set_session_message(REQUEST, 'info', msg)

        log.info("%s CREATED ORGANISATION %s", logged_in_user(REQUEST), org_id)

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/organisation?id=' + org_id)

    security.declareProtected(ldap_edit_orgs, 'edit_organisation_html')

    def edit_organisation_html(self, REQUEST):
        """ Edit organisation data """
        org_id = REQUEST.form['id']
        countries = get_country_options()

        options = {
            'countries': countries,
            'form_macro': get_template_macro('org_form_fields'),
        }

        session = REQUEST.SESSION
        if SESSION_FORM_DATA in session.keys():
            options['org_info'] = session[SESSION_FORM_DATA]
            del session[SESSION_FORM_DATA]
        else:
            options['org_info'] = self._get_ldap_agent().org_info(org_id)

        org_id = options['org_info']['id']
        self._set_breadcrumbs([(options['org_info']['id'],
                                self.absolute_url() + '/organisation?id=%s' %
                                org_id),
                               ('Edit Organisation', '#')])
        return self._render_template('zpt/orgs_edit.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'edit_organisation')

    def edit_organisation(self, REQUEST):
        """ Save modifications in the organisation data """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)

        errors = validate_org_info(org_id, org_info)
        if errors:
            msg = "Organisation not modified. Please correct the errors below."
            _set_session_message(REQUEST, 'error', msg)
            for msg in itertools.chain(*errors.values()):
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.SESSION[SESSION_FORM_DATA] = dict(org_info, id=org_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/edit_organisation_html?id=' + org_id)
            return

        agent = self._get_ldap_agent(bind=True)
        with agent.new_action():
            agent.set_org_info(org_id, org_info)

        when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _set_session_message(REQUEST, 'info', "Organisation saved (%s)" % when)

        log.info("%s EDITED ORGANISATION %s", logged_in_user(REQUEST), org_id)

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/organisation?id=' + org_id)

    security.declareProtected(ldap_edit_orgs, 'rename_organisation_html')

    def rename_organisation_html(self, REQUEST):
        """ Page for renaming an organisation """
        org_id = REQUEST.form['id']
        options = {
            'org_id': org_id,
        }
        self._set_breadcrumbs([(org_id,
                                self.absolute_url() + '/organisation?id=%s' %
                                org_id),
                               ('Rename Organisation', '#')])
        return self._render_template('zpt/orgs_rename.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'rename_organisation')

    def rename_organisation(self, REQUEST):
        """ Save modifications in the organisation id """
        org_id = REQUEST.form['id']
        new_org_id = REQUEST.form['new_id']
        if not re.match('^[a-z_]+$', new_org_id):
            _set_session_message(REQUEST, 'error', (VALIDATION_ERRORS['id']))
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/organisation?id=' + org_id)

        if org_id == new_org_id:
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/organisation?id=' + org_id)
            return

        agent = self._get_ldap_agent(bind=True)

        try:
            with agent.new_action():
                agent.rename_org(org_id, new_org_id)
        except NameAlreadyExists:
            msg = ('Organisation "%s" could not be renamed because "%s" '
                   'already exists.' % (org_id, new_org_id))
            _set_session_message(REQUEST, 'error', msg)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/organisation?id=' + org_id)
            return

        except OrgRenameError:
            msg = ('Renaming of "%s" failed mid-way. Some data may be '
                   'inconsistent. Please inform a system administrator.' %
                   org_id)
            _set_session_message(REQUEST, 'error', msg)
            REQUEST.RESPONSE.redirect(self.absolute_url() + '/')
            return

        msg = ('Organisation "%s" renamed to "%s".' % (org_id, new_org_id))
        _set_session_message(REQUEST, 'info', msg)

        log.info("%s RENAMED ORGANISATION %s TO %s",
                 logged_in_user(REQUEST), org_id, new_org_id)

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/organisation?id=' + new_org_id)

    security.declareProtected(ldap_edit_orgs, 'delete_organisation_html')

    def delete_organisation_html(self, REQUEST):
        """ Delete organisation page """
        org_id = REQUEST.form['id']
        options = {
            'org_info': self._get_ldap_agent().org_info(org_id),
        }
        self._set_breadcrumbs([(options['org_info']['id'],
                                self.absolute_url() + '/organisation?id=%s' %
                                org_id),
                               ('Delete Organisation', '#')])
        return self._render_template('zpt/orgs_delete.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'delete_organisation')

    def delete_organisation(self, REQUEST):
        """ Delete organisation """
        org_id = REQUEST.form['id']
        agent = self._get_ldap_agent(bind=True)
        with agent.new_action():
            agent.delete_org(org_id)

        _set_session_message(REQUEST, 'info',
                             'Organisation "%s" has been deleted.' % org_id)

        log.info("%s DELETED ORGANISATION %s", logged_in_user(REQUEST), org_id)

        REQUEST.RESPONSE.redirect(self.absolute_url() + '/')

    security.declarePublic('members_html')

    def members_html(self, REQUEST):
        """ view """

        org_id = REQUEST.form.get('id')
        if not org_id:
            _set_session_message(REQUEST, 'error',
                                 ("The organisation id is mandatory"))
            return REQUEST.RESPONSE.redirect(self.absolute_url())
        agent = self._get_ldap_agent()

        org_members = []
        members = agent.members_in_org(org_id)

        for user_id in members:
            try:
                org_members.append(agent.user_info(user_id))
            except (NO_SUCH_OBJECT, INVALID_DN_SYNTAX,
                    UserNotFound):
                deleted_user_info = dict((prop, '') for prop in USER_INFO_KEYS)
                deleted_user_info['first_name'] = 'Former'
                deleted_user_info['last_name'] = 'Member'
                deleted_user_info['full_name'] = 'Former Member'
                deleted_user_info['uid'] = user_id
                deleted_user_info['id'] = user_id
                deleted_user_info['dn'] = agent._user_dn(user_id)
                org_members.append(deleted_user_info)

        org_members.sort(key=operator.itemgetter('first_name'))
        options = {
            'organisation': agent.org_info(org_id),
            'org_members': org_members,
        }
        self._set_breadcrumbs([(org_id,
                                self.absolute_url() + '/organisation?id=%s' %
                                org_id),
                               ('Members', '#')])
        return self._render_template('zpt/orgs_members.zpt', **options)

    def notify_on_membership_op(self, user_info, org_info, operation):
        addr_from = ADDR_FROM
        addr_to = user_info['email']

        if operation == 'approval':
            email_template = load_template('zpt/org_membership_approved.zpt')
            subject = "%s: Approved organisation membership" % NETWORK_NAME
        elif operation == 'rejection':
            email_template = load_template('zpt/org_membership_rejected.zpt')
            subject = "%s: Rejected organisation membership" % NETWORK_NAME

        options = {
            'org_info': org_info,
            'user_info': user_info,
            'context': self,
            'network_name': NETWORK_NAME
        }
        message = _create_plain_message(
            email_template(**options).encode('utf-8'))
        message['From'] = addr_from
        message['To'] = user_info['email']
        message['Subject'] = subject

        try:
            mailer = getUtility(IMailDelivery, name="Mail")
            mailer.send(addr_from, [addr_to], message.as_string())
        except ComponentLookupError:
            mailer = getUtility(IMailDelivery, name="naaya-mail-delivery")
            mailer.send(addr_from, [addr_to], message)

    security.declareProtected(ldap_edit_orgs, 'demo_members')

    def demo_members(self, REQUEST):
        """ view """

        format = REQUEST.form.get('format', 'html')
        agent = self._get_ldap_agent()
        orgs_by_id = agent.all_organisations()

        orgs = []
        for org_id, info in orgs_by_id.iteritems():
            org_members = agent.members_in_org(org_id)
            members = []
            for user_id in org_members:
                try:
                    user_info = agent.user_info(user_id)
                    members.append(user_info)
                except (NO_SUCH_OBJECT, UserNotFound):
                    pass

            org = {
                'id': org_id,
                'name': info['name'],
                'country': info['country'],
                'members': members
            }
            orgs.append(org)

        orgs.sort(key=operator.itemgetter('name'))
        options = {
            'agent': agent,
            'orgs': orgs
        }

        if format == 'csv':
            from StringIO import StringIO
            import csv

            output = StringIO()
            header = ('Organisation ID', 'Organisation name', 'Member ID',
                      'Member full name', 'Member email')

            REQUEST.RESPONSE.setHeader('Content-Type', 'text/csv')
            REQUEST.RESPONSE.setHeader('Content-Disposition',
                                       "attachment;filename=ldap_users.csv")

            csv_writer = csv.writer(output)
            csv_writer.writerow(header)

            rows = []
            for org in orgs:
                if not org['members']:
                    row = [org['id'], org['name'], 'NO MEMEBRS', '', '']
                    rows.append(row)
                else:
                    user_data = org['members'][0]
                    first_row = [org['id'], org['name'], user_data['id'],
                                 user_data['full_name'], user_data['email']]
                    rows.append(first_row)
                    org['members'].pop(0)
                    for user_data in org['members']:
                        row = ['', '', user_data['id'], user_data['full_name'],
                               user_data['email']]
                        rows.append(row)

            for item in rows:
                csv_writer.writerow([value.encode('utf-8') for value in item])

            return codecs.BOM_UTF8 + output.getvalue()

        return self._render_template('zpt/orgs_html_report.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'remove_members')

    def remove_members(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        user_id_list = REQUEST.form['user_id']

        assert type(user_id_list) is list
        for user_id in user_id_list:
            assert type(user_id) is str

        agent = self._get_ldap_agent(bind=True)
        try:
            with agent.new_action():
                agent.remove_from_org(org_id, user_id_list)
            _set_session_message(REQUEST, 'info',
                                 'Removed %d members from organisation "%s".' %
                                 (len(user_id_list), org_id))

            log.info("%s REMOVED MEMBERS %s FROM ORGANISATION %s",
                     logged_in_user(REQUEST), user_id_list, org_id)

        except (NO_SUCH_OBJECT, INVALID_DN_SYNTAX,
                UserNotFound):
            _set_session_message(
                REQUEST, 'error',
                ("Deleted users cannot be removed from orgsnisations yet "
                 "(will be implemented)"))

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/members_html?id=' + org_id)

    security.declareProtected(ldap_edit_orgs, 'add_members_html')

    def add_members_html(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        search_query = REQUEST.form.get('search_query', u"")
        assert type(search_query) is unicode

        if search_query:
            agent = self._get_ldap_agent()
            found_users = agent.search_user(search_query)
        else:
            found_users = []

        found_active = [user for user in found_users
                        if user.get('status') != 'disabled']
        options = {
            'org_id': org_id,
            'search_query': search_query,
            'found_users': found_active,
            'found_inactive': len(found_active) != len(found_users)
        }
        self._set_breadcrumbs([(org_id,
                                self.absolute_url() + '/organisation?id=%s' %
                                org_id),
                               ('Members',
                                self.absolute_url() + '/members_html?id=%s' %
                                org_id),
                               ('Add Members', '#')])
        return self._render_template('zpt/orgs_add_members.zpt', **options)

    security.declareProtected(ldap_edit_orgs, 'add_members')

    def add_members(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        user_id_list = REQUEST.form['user_id']

        assert type(user_id_list) is list
        for user_id in user_id_list:
            assert type(user_id) is str

        agent = self._get_ldap_agent(bind=True)
        with agent.new_action():
            for user_id in user_id_list:
                old_info = agent.user_info(user_id)
                self._remove_from_all_orgs(agent, user_id)
                old_info['organisation'] = org_id
                agent.set_user_info(user_id, old_info)

            agent.add_to_org(org_id, user_id_list)

        _set_session_message(REQUEST, 'info',
                             'Added %d members to organisation "%s".' %
                             (len(user_id_list), org_id))

        log.info("%s ADDED MEMBERS %s TO ORGANISATION %s",
                 logged_in_user(REQUEST), user_id_list, org_id)

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/members_html?id=' + org_id)

    def can_edit_users(self, user=None):
        if user is None:
            user = self.REQUEST.AUTHENTICATED_USER
        return bool(user.has_permission(ldap_edit_users, self))

    def can_edit_members(self, user, org_id, member_id):
        """
        This could have been done as a decorator, but unfortunatelly
        Zope Publisher fails to match url address to callable when the
        arguments have arbitrary number

        """
        if user.name == 'Anonymous User':
            return False
        if self.can_edit_users(user):
            return True
        if not org_id:
            # top role - can_edit_users check was sufficient for granting
            return False

        agent = self._get_ldap_agent()
        org_members = agent.members_in_org(org_id)
        return member_id in org_members

    def _add_to_org(self, agent, org_id, user_id):
        try:
            agent.add_to_org(org_id, [user_id])
        except ldap.INSUFFICIENT_ACCESS:
            ids = self.aq_parent.objectIds(["LDAP Organisations Editor"])
            if ids:
                obj = self.aq_parent[ids[0]]
                org_agent = obj._get_ldap_agent(bind=True)
                org_agent.add_to_org(org_id, [user_id])
            else:
                raise

    def _remove_from_all_orgs(self, agent, user_id):
        orgs = agent.user_organisations(user_id)
        for org_dn in orgs:
            org_id = agent._org_id(org_dn)
            try:
                agent.remove_from_org(org_id, [user_id])
            except ldap.NO_SUCH_ATTRIBUTE:  # user is not in org
                pass
            except ldap.INSUFFICIENT_ACCESS:
                ids = self.aq_parent.objectIds(["LDAP Organisations Editor"])
                if ids:
                    obj = self.aq_parent[ids[0]]
                    org_agent = obj._get_ldap_agent(bind=True)
                    try:
                        org_agent.remove_from_org(org_id, [user_id])
                    except ldap.NO_SUCH_ATTRIBUTE:    # user is not in org
                        pass
                else:
                    raise

    def get_ldap_user_groups(self, user_id):
        """ """
        agent = self._get_ldap_agent(bind=True, secondary=True)
        ldap_roles = sorted(agent.member_roles_info('user',
                                                    user_id,
                                                    ('description',)))
        return ldap_roles


InitializeClass(OrganisationsEditor)


id_re = re.compile(r'^[a-z]{2}_[a-z]+$')
phone_re = re.compile(r'^\+[\d ]+$')
postal_code_re = re.compile(r'^[a-zA-Z]{2}[a-zA-Z0-9\- ]+$')

_phone_help = ('Telephone numbers must be in international notation (they '
               'must start with a "+" followed by digits which may be '
               'separated using spaces).')
VALIDATION_ERRORS = {
    'id': ('Invalid organisation ID. Mandatory format xx_yyyy - '
           'It must start with a two letter lowercase country code, '
           'followed by an underscore ("_") and then any number '
           'of lowercase a-z letters (no accented characters - unlike the '
           'title, which can contain any characters).'),
    'name': "The organisation's name is mandatory",
    'phone': "Invalid telephone number. " + _phone_help,
    'fax': "Invalid fax number. " + _phone_help,
    'postal_code': ('Postal codes must be in international notation (they '
                    'must start with a two-letter country code followed by a '
                    'combination of digits, latin letters, dashes and '
                    'spaces).'),
    'country': "The country name is mandatory",
}


def validate_org_info(org_id, org_info, create_mode=False):
    errors = {}

    if create_mode:
        if id_re.match(org_id) is None:
            errors['id'] = [VALIDATION_ERRORS['id']]

    name = org_info['name']
    if not name.strip():
        errors['name'] = [VALIDATION_ERRORS['name']]

    phone = org_info.get('phone')
    if phone and phone_re.match(phone) is None:
        errors['phone'] = [VALIDATION_ERRORS['phone']]

    fax = org_info.get('fax')
    if fax and phone_re.match(fax) is None:
        errors['fax'] = [VALIDATION_ERRORS['fax']]

    postal_code = org_info.get('postal_code')
    if postal_code and postal_code_re.match(postal_code) is None:
        errors['postal_code'] = [VALIDATION_ERRORS['postal_code']]

    # TODO Re-enable Country?
    # country = org_info.get('country')
    # if country and not country.strip():
    #     errors['country'] = [VALIDATION_ERRORS['country']]

    return errors
