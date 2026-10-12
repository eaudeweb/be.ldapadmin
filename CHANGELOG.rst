1.0 (unreleased)
------------------------
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

0.1 (2021-04-03)
------------------------
* initial merged version of eea.usersdb, eea.userseditor,
  eea.ldapadmin [valipod]
