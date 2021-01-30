''' changelog '''

from zope.component import getMultiAdapter
from zope.interface import Interface, Attribute, implements
from DateTime.DateTime import DateTime
from Products.Five import BrowserView


class IActionDetails(Interface):
    """ A view that presents details about user changelog actions
    """

    action_title = Attribute("Human readable title for this action")
    author = Attribute("Author of changes, in html format")
    details = Attribute("Action details in html format")


class BaseActionDetails(BrowserView):
    """ Generic implementation of IActionDetails
    """

    implements(IActionDetails)

    @property
    def action_title(self):
        raise NotImplementedError

    def details(self, entry):
        self.entry = entry
        return self.index()

    def author(self, entry):
        if entry['author'] == 'unknown user':
            return entry['author']

        user_info = self.context._get_ldap_agent().user_info(entry['author'])
        return u"%s (%s)" % (user_info['full_name'], entry['author'])

    def merge(self, roles):
        """ Merge the entries so that the only the leaf roles are displayed

        >>> roles = [
        ... 'eionet-group-mc-dk',
        ... 'eionet-group-mc',
        ... 'eionet-group',
        ... 'eionet',
        ... 'eionet-group-mc-se',
        ... 'eionet-group-mc',
        ... 'eionet-group',
        ... 'eionet',
        ... ]
        >>> print merge(roles)
        ['eionet-group-mc-dk', 'eionet-group-mc-se']
        """
        roles = sorted(roles)
        out = []
        last = len(roles) - 1
        for i, role in enumerate(roles):
            if i == last:
                out.append(role)
                break
            if role not in roles[i + 1]:
                out.append(role)

        return out


class EditedOrg(BaseActionDetails):
    """
    """

    action_title = "Edited organisation"


class CreatedOrg(BaseActionDetails):
    """
    """

    action_title = "Created organisation"


class RenamedOrg(BaseActionDetails):
    """
    """

    action_title = "Renamed organisation"

    def old_name(self):
        return self.context['data'][0]['old_name']


class AddedMemberToOrg(BaseActionDetails):
    """
    """

    action_title = "Added member to organisation"

    def member(self):
        return [x['member'] for x in self.context['data']]


class AddedPendingMemberToOrg(BaseActionDetails):
    """
    """

    action_title = "Added pending member to organisation"

    def member(self):
        return [x['member'] for x in self.context['data']]


class RemovedMemberFromOrg(BaseActionDetails):
    """
    """

    action_title = "Removed member from organisation"

    def member(self):
        return [x['member'] for x in self.context['data']]


class RemovedPendingMemberFromOrg(BaseActionDetails):
    """
    """

    action_title = "Removed pending member from organisation"

    def member(self):
        return [x['member'] for x in self.context['data']]


class OrganisationChangelog(BrowserView):
    """ Changelog for an organisation

    Context is an instance of OrganisationsEditor
    """

    def entries(self):
        org_id = self.request.form.get('id')
        agent = self.context._get_ldap_agent()
        org_dn = agent._org_dn(org_id)

        log_entries = list(reversed(agent._get_metadata(org_dn)))
        for entry in log_entries:
            date = DateTime(entry['timestamp']).toZone("CET")
            entry['timestamp'] = date.ISO()
            view = getMultiAdapter((entry, self.request),
                                   name="details_" + entry['action'])
            view.base = self.context
            entry['view'] = view

        output = []
        for entry in log_entries:
            if output:
                last_entry = output[-1]
                check = ['author', 'action', 'timestamp']
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

        return output


class BaseRoleDetails(BaseActionDetails):

    def details(self, entry):
        roles = [x['role'] for x in entry['data']]
        self.roles = self.merge(roles)
        return self.index()


class BaseOrganisationDetails(object):

    @property
    def organisation(self):
        out = []
        for entry in self.entry['data']:
            org = entry.get('organisation')
            if org:
                name = self.context._get_ldap_agent().org_info(
                    org.strip())['name']
                if not name:
                    name = org.title().replace('_', ' ')
                out.append({'id': org, 'name': name})

        return sorted(out, key=lambda x: x['id'])

    @property
    def organisation_id(self):
        out = []
        for entry in self.entry['data']:
            out.append(entry.get('organisation'))
        return sorted(out)


class EnableAccount(BaseActionDetails):
    """ Details for action ENABLE_ACCOUNT
    """

    action_title = "Enabled account"


class DisableAccount(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Disabled account"


class ResetAccount(BaseActionDetails):
    """ Details for action RESET_ACCOUNT
    """

    action_title = "User account reseted (roles deleted)"


class AddToOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action ADD_TO_ORG
    """

    action_title = "Added to organisation"


class RemovedFromOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action REMOVED_FROM_ORG
    """

    action_title = "Removed from organisation"


class AddPendingToOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action ADD_PENDING_TO_ORG
    """

    action_title = "Added pending to organisation"


class RemovedPendingFromOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action REMOVE_PENDING_TO_ORG
    """

    action_title = "Removed pending from organisation"


class AddedToRole(BaseRoleDetails):
    """ Details for action ADDED_TO_ROLE
    """

    action_title = "Added to role"


class RemovedFromRole(BaseRoleDetails):
    """ Details for action REMOVED_FROM_ROLE
    """

    action_title = "Removed from role"


class AddedAsRoleOwner(BaseActionDetails):
    """ Details for action ADDED_AS_ROLE_OWNER
    """

    action_title = "Added as role owner"


class RemovedAsRoleOwner(BaseActionDetails):
    """ Details for action REMOVED_AS_ROLE_OWNER
    """

    action_title = "Removed from role owner"


class AddedAsPermittedPerson(BaseActionDetails):
    """ Details for action ADDED_AS_PERMITTED_PERSON
    """

    action_title = "Added as permitted person"


class RemovedAsPermittedPerson(BaseActionDetails):
    """ Details for action REMOVED_AS_PERMITTED_PERSON
    """

    action_title = "Removed as permitted person"


class SetAsRoleLeader(BaseActionDetails):
    """ Details for action SET_AS_ROLE_LEADER
    """

    action_title = "Set as role leader"


class UnsetAsRoleLeader(BaseActionDetails):
    """ Details for action UNSET_AS_ROLE_LEADER
    """

    action_title = "Removed as role leader"


class SetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action SET_AS_ALTERNATE_ROLE_LEADER
    """

    action_title = "Added as alternate role leader"


class UnsetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action UNSET_AS_ALTERNATE_ROLE_LEADEg
    """

    action_title = "Removed as alternate role leader"
