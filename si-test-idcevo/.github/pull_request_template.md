<!--
    # This block is invisible on PR description
    #
    # If you would like to enable these options, please copy, remove heading
    # space and post outside the comment block.
    # Check also idcevo/test-automation repository for more options

    # Dirty build artifacts link
    # Note: define the link for build_artifacts.yaml
    # Example: ta_build_artifacts_file_url:https://idcevo.artifactory.cc.bmwgroup.net/artifactory/idcevo-platform-build-fg/check/github/idcevo/meta-idcevo/3278/2024-04-16-13-33-06/build_artifacts.yaml
    ta_build_artifacts_file_url:

    # SYSMAN_TESTING commit id or branch
    # Example: si_sysman_testing_version: pull/<zuul.change>/head or <branch-name>
    si_sysman_testing_version:

    # DELETION_HANDLER commit id or branch
    # Example: si_deletion_handler_version: pull/<zuul.change>/head or <branch-name>
    si_deletion_handler_version:

    # RSU_FLASHER_TOOL refspec
    # Example: si_rsu_flasher_tool_version: refs/changes/<refspec>
    si_rsu_flasher_tool_version:

    # BAT_AUTOMATION_TESTS commit id or branch
    # Example: si_bat_automation_tests_version: pull/<zuul.change>/head or <branch-name>
    si_bat_automation_tests_version:

    # BAT_AUTOMATION_TESTS_SYSTEMSW commit id or branch
    # Example: si_bat_automation_tests_systemsw_version: pull/<zuul.change>/head or <branch-name>
    si_bat_automation_tests_systemsw_version:

    # METRIC_COLLECTOR version
    # Note: These two pins should be defined together
    # Example:
    # si_metric_collector_package_version: <package_version>
    # si_metric_collector_index_url_default:"https://common.artifactory.cc.bmwgroup.net/artifactory/api/pypi/software-factory-pypi-dev/simple"
    si_metric_collector_package_version:
    si_metric_collector_index_url_default:

    # MTEE Core commit id
    # NOTE: generate dirty validation.
    ta_mtee_core_version:

    # MTEE Gen22 commit id
    # NOTE: generate dirty validation.
    ta_mtee_gen22_version:

    # MTEE APINext branch or commit id
    # NOTE: generate dirty validation.
    ta_mtee_apinext_repo_version:

    # tee-idcevo branch or commit id
    # NOTE: generate dirty validation.
    ta_tee_idcevo_version:

    # Use a mtee-sealed image release / dev release
    # The given value will be pushed to all sdk and *-mtf3-hw-* jobs
    # NOTE: generate dirty validation.
    ta_mtee_base_version:

    # Diagnose commit id
    # NOTE: generate dirty validation.
    ta_diagnose_version:

    # DLTLyse commit id
    # NOTE: generate dirty validation.
    ta_dltlyse_core_version:

    # DLTlyse plugins commit id
    # NOTE: generate dirty validation.
    ta_dltlyse_plugins_version:

    # Use a vcar image release / dev release
    # The given value will be pushed to all *-mtf3-hw-* jobs
    # NOTE: generate dirty validation.
    ta_vcar_version:

    # Test suite to execute in test jobs
    ta_tee_test_suite: SI-staging
-->
