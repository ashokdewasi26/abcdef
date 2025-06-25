# PINNED versions
Meaning they are expected to be temporary
- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-base
    - [**vcar_version**: "2025.05.07.1" # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L10)
    - [**dltlyse_plugins_version**: "686e84f24a4772581cc6a4077cec7c40deaf9a6c" # TEMP_PIN due to changes not in main image (https://cc-github.bmwgroup.net/node0/dltlyse-plugins-gen22/pull/453)](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/8e6859760d50bab2cb0523b06a516652f1f0d229/zuul.d/jobs/jobs-SI-idcevo.yaml#L33)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-production
    - [**validation_python_esys_version**: fix_unsigned_path_tokens  # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L432)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-GED4K
    - [**queue**: tf-worker-idcevo-049  # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L462)

- si-idcevo-ee25-traas-SI-base
    - [**mtee_apinext_version**: "master" # TEMP_PIN Pinned for now, when removing also remove from extra_prepare_actions](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-traas.yaml#L39)
    - [**si_test_idcevo_si_version**: "master" # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-traas.yaml#L40)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SP21-SI-base
    - [**dltlyse_plugins_version**: "686e84f24a4772581cc6a4077cec7c40deaf9a6c" # TEMP_PIN due to changes not in main image (https://cc-github.bmwgroup.net/node0/dltlyse-plugins-gen22/pull/453)](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/8e6859760d50bab2cb0523b06a516652f1f0d229/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L31)

- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI-base
    - [**dltlyse_plugins_version**: "686e84f24a4772581cc6a4077cec7c40deaf9a6c" # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/8e6859760d50bab2cb0523b06a516652f1f0d229/zuul.d/jobs/jobs-SI-rse26.yaml#L17)

- ta-cde-hw-mtf3-flash-and-validate-cde-SI-base
    - [**dltlyse_plugins_version**: "686e84f24a4772581cc6a4077cec7c40deaf9a6c" # TEMP_PIN](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/8e6859760d50bab2cb0523b06a516652f1f0d229/zuul.d/jobs/jobs-SI-cde.yaml#L17)

# Other versions in use
These are currently defined and they can remain like they are until it makes sense or it's necessary to update them

- playbooks/build-tee-test-config/si-test-run-build-tee.yaml
    - [**python_version**: "3.10"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/playbooks/build-tee-test-config/si-test-run-build-tee.yaml#L10)
    - [**build_tee_version**: "1.10.6"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/playbooks/build-tee-test-config/si-test-run-build-tee.yaml#L60)

- playbooks/traas/traas-run-build-tee.yaml
    - [**build_tee_version**: "1.10.2"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/playbooks/traas/traas-run-build-tee.yaml#L33)

- roles/ensure-testing-reporting/defaults/main.yaml
    - [**metric_collector_package_version**: "1.4.1"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/roles/ensure-testing-reporting/defaults/main.yaml#L2)

- zuul.d/jobs/regular-jobs.yaml
    - [**test_summarizer_package_version**: "1.0.4"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/f39496615dd939c6f5c5f0ad61f86f5d3f7a8450/zuul.d/jobs/regular-jobs.yaml#L19)
    - [**cde_launcher_app_version**: "UI_Tests_vcar" # Pinned version due to CDE Launcher App Tests](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/regular-jobs.yaml#L104)
    - [**rse_launcher_app_version**: "UI_Tests_vcar" # Pinned version due to RSE Launcher App Tests](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/regular-jobs.yaml#L105)

## IDCevo pu2507
- idcevo-pu2507-user-SI-STR
    - [**sysman_testing_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-pu2507.yaml#L207)
- idcevo-pu2507-user-STR-SIT-Automated
    - [**sysman_testing_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-pu2507.yaml#L221)

## IDCevo TRAAS Mainline
- si-idcevo-ee25-traas-SI-base
    - [**mtee_apinext_version**: "master" # TEMP_PIN Pinned for now, when removing also remove from extra_prepare_actions](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-traas.yaml#L39)
    - [**si_test_idcevo_si_version**: "master" # TEMP_PIN This will not install the test-suites and test packages, just installs the repo into the docker](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-traas.yaml#L40)

## IDCevo Mainline
- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-base
    - [**mtee_apinext_repo_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L28)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-kpi-test
    - [**sofya_lib_version**: 0.3.8](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L104)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI
    - [**rsu_flasher_tool_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L143)
    - [**partition_manager_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L144)
    - [**sysman_testing_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L145)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-staging
    - [**bat_automation_tests_systemsw_version**: "si_job_ready"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L235)
    - [**bat_automation_tests_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L236)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-domains
    - [**bat_automation_tests_systemsw_version**: "si_job_ready"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L312)
    - [**bat_automation_tests_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L313)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-long
    - [**sofya_lib_version**: 0.3.8](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L299)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-lifecycle
    - [**sysman_testing_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L366)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-kpi-reboots
    - [**sofya_lib_version**: 0.3.8](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo.yaml#L355)

## IDCevo SP21
- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SP21-SI-base
    - [**mtee_apinext_repo_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L26)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SP21-SI
    - [**rsu_flasher_tool_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L94)
    - [**partition_manager_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L95)
    - [**sysman_testing_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L96)

- ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SP21-SI-staging
    - [**bat_automation_tests_systemsw_version**: "si_job_ready"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L123)
    - [**bat_automation_tests_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-idcevo-SP21.yaml#L124)

## CDE
- ta-cde-hw-mtf3-flash-and-validate-cde-SI-base
    - [**mtee_apinext_repo_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L11)

- ta-cde-hw-mtf3-flash-and-validate-cde-SI
    - [**partition_manager_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L76)

- ta-cde-hw-mtf3-flash-and-validate-cde-SI-staging
    - [**bat_automation_tests_systemsw_version**: "si_job_ready"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L93)
    - [**bat_automation_tests_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L94)

- ta-cde-hw-mtf3-flash-and-validate-cde-SI-performance
    - [**sofya_lib_version**: 0.3.8](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L127)

- ta-cde-hw-mtf3-cde-SI-PDX-flashing-stress
    - [**rsu_flasher_tool_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L142)

- ta-cde-hw-mtf3-flash-and-validate-cde-SI-android
    - [**cde_launcher_app_version**: "UI_Tests_vcar" # Pinned version due to CDE Launcher App Tests](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-cde.yaml#L164)

## RSE26 Mainline
- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI-base
    - [**mtee_apinext_repo_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L11)

- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI
    - [**rsu_flasher_tool_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L77)
    - [**partition_manager_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L83)

- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI-performance
    - [**sofya_lib_version**: 0.3.8](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L109)

- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI-staging
    - [**bat_automation_tests_systemsw_version**: "si_job_ready"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L132)
    - [**bat_automation_tests_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L133)

- ta-rse26-hw-mtf3-rse26-SI-PDX-flashing-stress
    - [**rsu_flasher_tool_version**: "master"](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L154)

- ta-rse26-hw-mtf3-flash-and-validate-rse26-SI-android
    - [**rse_launcher_app_version**: "UI_Tests_vcar" # Pinned version due to RSE Launcher App Tests](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/0bbe87ad000682d68b64f8815dbf9e546f81c367/zuul.d/jobs/jobs-SI-rse26.yaml#L169)