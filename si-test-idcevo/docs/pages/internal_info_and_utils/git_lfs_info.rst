Adding LFS file to the repository
---------------------------------

Precondition: Git LFS must be enabled in the repository. See as step 1: `Git_LFS`_ and as step 2: `PR`_.

When adding a new LFS file follow below steps:

* Follow steps 1-2, 3-4(if necessary to add new type of file), 7 and 8 in `Git_LFS`_;
* While pushing the file, git will ask for the username and password. Go to `user_profile`_ and click on: **Welcome, <user_name>** (top right corner) -> **Edit Profile** -\> **Generate an Identity Token**  if you don't have a generated token yet;
* Use the **<user_name>** and **<Reference Token ID>** appearing in the dialog box as username & password. Save it for later use;
* Once generated the token is valid for 12 months.

.. _Git_LFS: https://confluence.cc.bmwgroup.net/display/ccdoc/Git+LFS
.. _PR: https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/pull/290
.. _user_profile: https://apinext.artifactory.cc.bmwgroup.net/ui/