# Write a new test

Before writing a new test you might want to be familiar with how we have or repo organized. [Repo structure](../internal_info_and_utils/organization_of_the_repo.rst)

After that you should identify the proper test package based on your ticket domain.
The test should be added inside the test file that contains similar tests unless there is None, in that case you can create a new one.

## In practice (some tips):

### Basic test case skeletons

As an example of tests that can be executed, you can find the folder Examples. There are a couple of tests, in use at this moment. For a better and deeper explanation, some documentation can be found [HERE](https://cc-github.bmwgroup.net/pages/node0/tee-node0/examples.html#usage-examples).

***TIP:***
- Test files must end in ```_tests.py```;
- Method must start with ```def test_```;
- tags like ```@metadata(testsuite=["SI"])``` are needed and should be filled with the metadata related to your ticket.

### Full traceability metadata
We need to fill the proper metadata for each test.
This is the common metadata we follow:
```python
@metadata(
    testsuite=["SI"],
    component="tee_idcevo",
    domain="LinuxOS",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-12835",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
        },
    },
)
def test_005_kernel_event_tracing_for_net_group(self):
```

The specific details to each test are:
- **domain** -> can be seen by the ticket domain details
- **duplicates** -> the jira ticket of type "test" with the requirement steps
- **traceability** -> we have a file with all the feature ticket on the si_test_config - [idcevo_config.ini](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/idcevo_config.ini) (same is available for RSE26 - [rse26_config.ini](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/rse26_config.ini))
  - You should add here a new feature ticket.
  - The feature ticket usually is linked to the one mentioned on duplicates and is from PM (project management) e.g. IDCEVOPM-4769


## Run a test from other repo

### Are they already packed in the image? and so present at the TEE?
Just list them on a test suite, like: [https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/test-suites/SI-staging-systemtests-idcevo](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/test-suites/SI-staging-systemtests-idcevo) and make sure the job you trigger is running this test suite.

### Do you need to pack them?
Check: [https://cc-github.bmwgroup.net/software-factory/validation-build-tee#readme](https://cc-github.bmwgroup.net/software-factory/validation-build-tee#readme)

# Test related with bootlog

If your test intend to search for a specific marker on the bootlog we have a generic way to collect that similar to generic DLT KPI.

In this case you only need to add a new entry on:
 - [search_bootlog_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/search_bootlog_config.py)

All the entries in this config file will be processed by the [search_bootlog_tests.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_package_basic/posttests/search_logs_tests.py).

In more depth, we collect the full bootlog on one of the boots of the target and then this last post test just goes through it at the post test phase.
