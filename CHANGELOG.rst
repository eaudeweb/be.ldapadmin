0.4 (unreleased)
----------------

0.3 (2026-10-20)
----------------
* fix the member search failing with IndexError in agent_from_uf when the
  LDAP server does not answer: raise LDAPUnavailable instead [dumitval]

0.2 (2026-10-15)
----------------
* Find organisations by the organizationGroup object class used in the LDAP
  [dumitval]
* Fix generate_user_id using min(str, int) for the first name length
  [dumitval]
* Fix create_user adding the user to one organisation per character when a
  single organisation is selected [dumitval]
* Fix find_duplicates failing when first name, last name or email is
  missing [dumitval]
* Fix the table-user-info macro failing on the undefined role_id when the
  membership type column is hidden (find_duplicates) [dumitval]
* Remove duplicate addresses from the bulk_get_emails result [dumitval]
* Read the "Telephone Number" column of the bulk user import template
  [dumitval]
* Save the remove_permittedPerson change record on the user DN instead of
  the user id [dumitval]
* Store the permittedPerson and owner roles removed by disable_user and
  reset_user_roles, so enable_user can restore them; restore the ownership
  of each role only, not of its sub-roles [dumitval]
* Show the result page after the roles import instead of an empty response,
  and remove the role rename, merge and prefill steps disabled since 2014
  [dumitval]
* Do not make the hard-coded, non-existent user nerifern owner of the
  roles created by the roles import [dumitval]
* Default orgs_dn for configs saved without it [dumitval]
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

0.1 (2021-04-03)
------------------------
* initial merged version of eea.usersdb, eea.userseditor,
  eea.ldapadmin [valipod]
