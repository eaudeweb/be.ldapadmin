''' query module '''
from AccessControl import ClassSecurityInfo
from OFS.PropertyManager import PropertyManager
from OFS.SimpleItem import SimpleItem
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from .ui_common import CommonTemplateLogic, TemplateRenderer

manage_add_query_html = PageTemplateFile('zpt/query_manage_add.zpt', globals())


def manage_add_query(parent, query_id, title, pattern, REQUEST=None):
    """ Create a new Query object """
    obj = Query()
    obj._setId(query_id)
    obj.title = title
    obj.pattern = pattern
    parent._setObject(query_id, obj)

    if REQUEST is not None:
        url = parent.absolute_url() + '/manage_workspace'

        return REQUEST.RESPONSE.redirect(url)


class Query(SimpleItem, PropertyManager):
    ''' An Eionet roles editor query '''
    meta_type = 'Eionet Roles Editor Query'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-www/roles_query.gif'

    manage_options = PropertyManager.manage_options + (
        {'label': 'View', 'action': ''},
    ) + SimpleItem.manage_options

    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w', 'label': 'Title'},
        {'id': 'pattern', 'type': 'string', 'mode': 'w', 'label': 'Pattern'},
    )

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def _get_ldap_agent(self):
        ''' get the ldap agent '''
        return self.aq_parent._get_ldap_agent()

    def index_html(self, REQUEST):
        """ view """

        return self.aq_parent._filter_results(
            self.pattern, 'Predefined search query - ' + self.title)
