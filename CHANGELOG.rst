1.6 (unreleased)
----------------

1.5 (2026-10-23)
----------------
* Give the methods with a blank docstring a text: Python 3.13 strips it to ''
  and Zope does not publish methods without a docstring [dumitval]

1.4 (2026-10-18)
----------------
* Fix the member search failing with IndexError in agent_from_uf when the
  LDAP server does not answer: raise LDAPUnavailable instead [dumitval]

1.3 (2026-10-17)
----------------
* Read the countries from countries.json in the package (the 27 EU
  countries, the European Union and the United Kingdom) instead of
  LDAP_DISK_STORAGE; a missing file stopped the product from loading
  [dumitval]

1.2 (2026-10-16)
----------------
* Use jellyfish.jaro_winkler_similarity and require jellyfish >= 1.0
  [dumitval]
* Remove the unused sparql-client requirement [dumitval]

1.1 (2026-10-16)
----------------
* Default orgs_dn for configs saved without it [dumitval]
* Do not make the hard-coded, non-existent user nerifern owner of the
  roles created by the roles import [dumitval]
* Fix generate_user_id failing on min(str, int) and string.lowercase
  [dumitval]
* Read countries.json as UTF-8 [dumitval]
* Fix create_user adding the user to one organisation per character when a
  single organisation is selected [dumitval]
* Fix find_duplicates failing when first name, last name or email is
  missing [dumitval]
* Fix the table-user-info macro failing on the undefined role_id when the
  membership type column is hidden (find_duplicates) [dumitval]
* Remove duplicate addresses from the bulk_get_emails result [dumitval]
* Read the "Telephone Number" column of the bulk user import template
  [dumitval]
* Fix remove_from_org failing on NO_SUCH_ATTRIBUTE: use e.args[0]
  [dumitval]
* Decode the uid read from LDAP in _user_id for non-uid RDNs [dumitval]
* Save the remove_permittedPerson change record on the user DN instead of
  the user id [dumitval]
* Remove the unused UsersAdmin.change_password views [dumitval]
* Read .xlsx files in the bulk user and roles imports (openpyxl instead of
  xlrd) [dumitval]
* Export the organisation lists as .xlsx (xlsxwriter instead of xlwt)
  [dumitval]
* Serve the bulk user template as create_users_template.xlsx with the .xlsx
  content type [dumitval]
* Show the result page after the roles import instead of an empty response,
  and remove the role rename, merge and prefill steps disabled since 2014
  [dumitval]

1.0 (2026-10-12)
----------------
* Port to Python 3 and Zope 5 [dumitval]
* Require naaya.ldapdump >= 2.0.0, allow newer jellyfish releases [dumitval]
* Reinstate role_id as grouping, sorting criterion on Excel export [valipod]
* Highlight deactivated roles: set role status to "Terminated" on
  deactivation, sort roles listing by active/inactive, visually mark
  inactive roles [valipod]
* Show "Export all members" button also on top-level role;
* hide "All members" button when already on that page [valipod]
* Switch Excel export library from xlwt to xlsxwriter [valipod]
* Sort users inside role listings by name [valipod]
* Role membership type: store, edit, filter, and export membership type
  per user in roles (stored on destinationIndicator attribute)
  [batranud, valipod]
* Role activate/deactivate support with status tracking and export [batranud]
* Role description stored in postalAddress and included in export [batranud]
* Merge role name and description cells in export [batranud]
* Group "All members" export by role [batranud]
* Include role information in export regardless of subroles option [batranud]
* Link to role details instead of just displaying the role id [valipod]
* Use PEP 420 namespace packages [dumitval]
* Fix the country options on Python 3 [dumitval]
* Fix the users search page on Python 3 [dumitval]
* Fix the organisations Excel exports on Python 3 [dumitval]
* Fix organisation countries and members, user organisations, existing
  emails, the password length message and the breadcrumbs on Python 3
  [dumitval]
* Find organisations by the organizationGroup object class used in the LDAP
  [dumitval]
* Send LDAP attribute values as bytes when adding and modifying entries
  [dumitval]
* Fix the user details page on Python 3 [dumitval]
* Replace the deprecated datetime.utcnow [dumitval]
* Fix the user create and edit forms on Python 3 [dumitval]
* Fix the role users CSV export on Python 3 [dumitval]
* Use the standard library json instead of simplejson [dumitval]
* Store role ids instead of consumed generators for roles_permittedPerson and
  roles_owner in the DISABLE_ACCOUNT and RESET_ACCOUNT change records
  [dumitval]
* Restore role memberships, permittedPerson and role ownership when a user is
  re-enabled with restore, skip and report roles deleted meanwhile [dumitval]
* Replace the restore_roles checkbox on the enable user page with "Restore
  all" / "Restore nothing" radio buttons [dumitval]
* Store only the restored items in the ENABLE_ACCOUNT change record
  [dumitval]

0.1 (2021-04-03)
------------------------
* initial merged version of eea.usersdb, eea.userseditor,
  eea.ldapadmin [valipod]
