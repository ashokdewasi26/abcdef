# How to have your (domain) tests running on SI

## Scenario 1: your tests are not packed in the image build
- Consider doing the exercise of planning the steps needed to have your tests integrated in the build image:
    - Figure out what is the structure they should have while running
    - How would the .bb file would look like?
        - Only need to pack tests? [example](https://cc-github.bmwgroup.net/idcevo/meta-idcevo/blob/master/recipes-testing/lifecycle-powermanagement-bat/lifecycle-powermanagement-bat.bb)
        - Some disperse enablers? [example](https://cc-github.bmwgroup.net/idcevo/meta-idcevo/blob/master/recipes-testing/audio-bat/audio-bat.bb)
    - Example of the file necessary to have a new test package in the image build: [example](https://cc-github.bmwgroup.net/idcevo/meta-idcevo/blob/master/recipes-testing/si-performance/si-performance.bb)
- In case you don't want your tests integrated in the image build you can install them at run time
    - To do this you need to translate the steps above into build-tee inputs. Read this carefully: [build-tee readme](https://cc-github.bmwgroup.net/software-factory/validation-build-tee#readme)
    - Example of translation to build-tee inputs:
        - This [.bb file](https://cc-github.bmwgroup.net/idcevo/meta-idcevo/blob/master/recipes-testing/si-performance/si-performance.bb) which produces the 'si-performance' test package
        - Translates directly in this [build-tee instructions](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/683a768ec75c28bf540a6a40d008180739dd2ed6/playbooks/build-tee-test-config/templates/tests-config.yaml.j2#L94-L118), meaning, they produce the exact same output
    - These steps should be applied on the 'tests' section at [this file](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/playbooks/build-tee-test-config/templates/tests-config.yaml.j2)
    - The resulting test package can be checked after running a job with these steps on the results folder: "test-env/build-tee/build/test-execution-environment/tests/"
- After having your tests/test package available in the TEE at runtime (either by installing them with build-tee or by packing them with the image build) just go to scenario 2 and follow all the steps

## Scenario 2: your tests are already packed in the image build
- Just selected them to run! How? See these steps:
    - Add you package name on [systemtests suite](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/test-suites/SI-domains-systemtests-idcevo)
    - If you have posttests, add your package to [posttests suite](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/test-suites/SI-domains-posttests-idcevo)
    - Run a staging job by editing the [test pipeline file](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/zuul.d/pipelines/test.yaml)
        - Edit this file to run a staging job with the test suite you just edited. Here is what it should look like: [example](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/f97d21b298a8730eeff0513f19f3968b3cb5a1db/zuul.d/pipelines/test.yaml)
        - In case you want to try to upload your test results to Jira leave the variable 'enable_jira_xrayctl_upload' uncommented
        - Write a comment on the conversation of your PR with 'retest' , [example](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/pull/276#issuecomment-10814323)
        - Check the results of the execution in zuul, [example](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/pull/276#issuecomment-10816796)
            - The most user friendly place to see the test results is the file "test_results.html" on the root of the results (once in a zuul job page click on the "Logs" tab and you should find it there)
        - In case you set the 'enable_jira_xrayctl_upload' to True, check the [results in Jira](https://jira.cc.bmwgroup.net/browse/IDCEVODEV-28333)
- After having your changes merged and your tests running in the SI-domains production job you can check the results here:
    - [Zuul](https://cc-ci.bmwgroup.net/zuul/t/idcevo/builds?job_name=ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-domains&project=idcevo%2Fsi-test-idcevo&branch=master&pipeline=nightly-late%09&skip=0)
    - [Jira](https://jira.cc.bmwgroup.net/browse/IDCEVODEV-68689)
