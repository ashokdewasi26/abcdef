# How to test with TRAAS

## TRAAS racks that are currently being used

- IDCEVO SITA Rack CoCo_020
- IDCEVO SITA Rack CoCo_021

P.S: This list was updated on 28/10/2024.

Check TRAAS website to verify if there is any other rack available

## How to Run Tests in the **si-test-idcevo** Repository Using TRAAS

To run tests in the **si-test-idcevo** repository, you must use the **si-idcevo-ee25-traas-SI-staging** job. This job is already configured to incorporate the changes made in the PR.

1. **Edit `test.yaml`**:
    - Open the `test.yaml` file in your repository.
    - Add the following configuration to specify the job to run:

    ```yaml
    - project:
        test:
            jobs:
                - si-idcevo-ee25-traas-SI-staging
    ```

2. **Edit Test Packages**:
    - Update the `SI-staging-traas-posttests-idcevo` and `SI-staging-traas-systemtests-idcevo` files with the test packages you want to run. Ensure that the test packages are correctly specified to cover the necessary test cases.

3. **Create a PR and trigger the tests**:
    - Commit your changes and create the PR.
    - In the PR comments, type **retest** to trigger the tests. This command will initiate the testing process using the specified job and test packages.

### Additional Information

- **Supported Variables**: For more information on the variables that are supported and used in our jobs, refer to the next section. These variables can help you customize the testing process to suit your needs.

By following these steps, you can effectively run tests in the **si-test-idcevo** repository using TRAAS, ensuring that your changes are thoroughly tested before merging.

## Understanding TRAAS playbook variables

- ```rack_tags```: define the racks where the job runs. **Note:** Insert here the label of rack not the name.
- ```extra_prepare_actions```: Define extra traas actions. Check traas repository to see all available actions
- ```test_suite```: Define the test suite to run
- ```flash_dev_full```: If this variable is set as true, the dev flash will be executed on preparing the TRAAS workspace
- ```executor_version```: Use this if you had any custom TRAAS build. Define the QX-number associated with that build

## Dummy test suite & job

The dummy test suite is designed to perform specific tests on a periodic basis, either daily or weekly, to monitor the status of CTW racks.

This test suite includes basic tests for both Linux and Android components to ensure the integrity of the rack, with a primary focus on IDCEVO. Additionally, it contains tests to collect metrics and KPIs.

This job can be triggered by using `ee25-traas-CTW-Rack-Health-base` and set a rack to run on