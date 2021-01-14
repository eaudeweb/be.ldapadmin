""" INIT for the LDAP administration tools """

from db_agent import UsersDB, editable_user_fields, editable_org_fields
from db_agent import (OrgRenameError, NameAlreadyExists, RoleNotFound,
                      UserNotFound)
from schema import user_info_schema


__all__ = [UsersDB.__name__, editable_user_fields.__repr__(),
           editable_org_fields.__repr__(), OrgRenameError.__name__,
           NameAlreadyExists.__name__, RoleNotFound.__name__,
           UserNotFound.__name__, user_info_schema.title]


def initialize(context):
    ''' initialize '''
    import roles_editor
    import orgs_editor
    import pwreset_tool
    import users_admin
    import api_tool
    import dashboard
    import logger
    import countries
    import users_editor
    import userdetails

    countries.load_countries()
    logger.init()

    context.registerClass(roles_editor.RolesEditor, constructors=(
        ('manage_add_roles_editor_html',
         roles_editor.manage_add_roles_editor_html),
        ('manage_add_roles_editor', roles_editor.manage_add_roles_editor),
    ))

    context.registerClass(orgs_editor.OrganisationsEditor, constructors=(
        ('manage_add_orgs_editor_html',
         orgs_editor.manage_add_orgs_editor_html),
        ('manage_add_orgs_editor', orgs_editor.manage_add_orgs_editor),
    ))

    context.registerClass(pwreset_tool.PasswordResetTool, constructors=(
        ('manage_add_pwreset_tool_html',
         pwreset_tool.manage_add_pwreset_tool_html),
        ('manage_add_pwreset_tool', pwreset_tool.manage_add_pwreset_tool),
    ))

    context.registerClass(users_admin.UsersAdmin, constructors=(
        ('manage_add_users_admin_html',
         users_admin.manage_add_users_admin_html),
        ('manage_add_users_admin', users_admin.manage_add_users_admin),
    ))

    context.registerClass(api_tool.ApiTool, constructors=(
        ('manage_add_api_tool', api_tool.manage_add_api_tool),
    ))

    context.registerClass(dashboard.Dashboard, constructors=(
        ('manage_add_ldap_admin_html',
         dashboard.manage_add_ldap_admin_html),
        ('manage_add_ldap_admin', dashboard.manage_add_ldap_admin),
    ))

    # Init for userseditor
    constructors = (
        ('manage_addUsersEditor_html',
         users_editor.manage_addUsersEditor_html),
        ('manage_addUsersEditor', users_editor.manage_addUsersEditor),
    )
    context.registerClass(users_editor.UsersEditor, constructors=constructors)

    context.registerClass(userdetails.UserDetails, constructors=(
        ('manage_add_userdetails_html',
         userdetails.manage_add_userdetails_html),
        ('manage_add_userdetails', userdetails.manage_add_userdetails),
    ))
