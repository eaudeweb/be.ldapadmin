''' LDAP config and methods '''

from be.ldapadmin.db_agent import UsersDB
from be.ldapadmin.logic_common import logged_in_user, load_template

defaults = {
    'admin_dn': "cn=Manager,dc=CIRCA,dc=local",
    'admin_pw': "",
    'ldap_server': "127.0.0.1",
    'users_rdn': 'uid',
    'users_dn': "ou=Users,ou=DATA,ou=america,o=IRCusers,dc=CIRCA,dc=local",
    'orgs_dn': "ou=DATA,ou=america,o=IRCorganisations,dc=CIRCA,dc=local",
    'roles_dn': "ou=DATA,ou=america,o=IRCroles,dc=CIRCA,dc=local",
    'secondary_admin_dn': "cn=Manager,dc=CIRCA,dc=local",
    'secondary_admin_pw': "",
}


def read_form(form, edit=False):
    config = dict((name, form.get(name, default))
                  for name, default in defaults.iteritems())
    if edit:
        if not config['admin_pw'].strip():
            del config['admin_pw']
        if not config['secondary_admin_pw'].strip():
            del config['secondary_admin_pw']
    return config


def ldap_agent_with_config(config, bind=False, secondary=False):
    db = UsersDB(ldap_server=config['ldap_server'],
                 # next is for bwd compat with objects created with v1.0.0
                 users_rdn=config.get('users_rdn', defaults['users_rdn']),
                 users_dn=config['users_dn'],
                 orgs_dn=config['orgs_dn'],
                 roles_dn=config['roles_dn'])

    if bind:
        if secondary:
            db.perform_bind(config['secondary_admin_dn'],
                            config['secondary_admin_pw'])
        else:
            db.perform_bind(config['admin_dn'], config['admin_pw'])

    return db


def _get_ldap_agent(context, bind=False, secondary=False):
    ''' get the ldap agent '''
    agent = ldap_agent_with_config(context._config, bind,
                                   secondary=secondary)
    try:
        agent._author = logged_in_user(context.REQUEST)
    except AttributeError:
        agent._author = "System user"

    return agent


edit_macro = load_template('zpt/ldap_config.zpt').macros['edit']
