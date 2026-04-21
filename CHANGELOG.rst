0.2 (unreleased)
------------------------
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
