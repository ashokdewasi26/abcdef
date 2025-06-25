Additional notes on the organization of the repository
======================================================

Repo structure
------------------------------

We have the test files grouped by domain test package and we also group the tests that have the same topic on the same file.

Folder structure:

.. code-block:: text

    |- si_test_config (configurations related to some test files and generic KPI)
    |- si_test_data (some tarball and files we want to be upload to /resources on the tests)
    |- si_test_helpers (common helpers files across test packages)
    |- si_test_package_linuxos
    |- si_test_package_performance
    |- |- posttests		(folder for posttests)
    |- |- tests		(folder for tests)
    |- |- |- generic_dlt_kpi_tests.py (test file to add tests)
    |- test-suites		(configurations test)
    |- zuul.d 		(configurations job)

Test package naming convention
------------------------------

si\_test\_package\_\ **EcuName**\_\ **TestEnv**\_PackageName

1. EcuName - Ecu name : eg: idcevo
2. TestEnv - Test Environment (farm, traas, if common set nothing)

Test packages naming examples
`````````````````````````````

1. Common test package (applicable for all ECUs): si\_test\_package\_name
2. Specific test package for idcevo running on TF (only worker config): si\_test\_package\_idcevo\_farm\_package\_name
3. Specific test package for idcevo running on TRAAS (only TRAAS config): si\_test\_package\_idcevo\_traas\_package\_name

If you need to create a new test package please take a look at this link: `Create a new job, suite and test package <https://asc.bmwgroup.net/wiki/pages/viewpage.action?pageId=849286071>`_


Job organization convention
---------------------------

SI jobs should inherit from the **ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-base** defined on **zuul.d/jobs/jobs-SI-idcevo.yaml**

The goal of this base job is to group and define all the necessary variables with default values and examples as comments.
This job can be considered a staging job where all the useful variables are explicitly defined, however it is not
regularly executed (it's not directly called by any recurrent trigger like daily triggered jobs).
All other jobs should inherit from this base, making sure the 'staging area' is always functional.
This base job inherits from test-automation job **ta-idcevo-hw-mtf3-flash-and-validate-idcevo** so most variables have
default values already defined there, however for easy understanding/double-check we agreed to redefine the most relevant here.

Control the install of SI tests
-------------------------------

Currently no SI tests or test suites are integrated on the build image files. This install can be performed at runtime by enabling
the boolean variable: **install_si_tests_idcevo**.
Although the variables **si_test_idcevo_si_version** and **install_si_tests_idcevo** are related each has a different function. The
**si_test_idcevo_si_version** variable defines which version of the repository should be used, such as master, branch name, or tag name.
Setting this variable guarantees that the si-test-idcevo repository is installed as a whole, i.e. the executables and entry points defined
in the repository configuration are available, however, this will not install the tests in the TEE test folder. If this variable is not defined,
the repository will not be installed and will not be available because it is currently not packaged in the image.
The **install_si_tests_idcevo** variable allows the installation of tests and test suites on the TEE. In the case this variable is set to: *true*,
and the variable **si_test_idcevo_si_version** is not defined, there will be a forced definition of **si_test_idcevo_si_version** to 'master', otherwise
the tests will be installed with the defined **si_test_idcevo_si_version**. Consequently the si-test-idcevo repository will be installed.
Again, if this variable is not defined, the si-tests will not be installed and will not be available because they are currently not packaged in the image.
