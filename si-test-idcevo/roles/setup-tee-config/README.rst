The role will generate a build-tee configuration variable `tee_config` (Ansible fact)
based on the input version variables for the test execution environment
versions.

The template for build-tee configuration object can be found in the defaults.
There, one can adjust the repositories that build-tee will use when assembling
the testing environment.

**Role variables**

.. zuul:rolevar:: si_test_idcevo_si_version
    The version of the repository https://cc-github.bmwgroup.net/idcevo/si-test-idcevo
    to be used when building the test environment.

.. supported_os:: Linux, Windows

.. reusable:: True
