# si-test-apinext

### Staging jobs

The following topics are about the staging jobs setup on this repo.
There is also a step-by-step guide on how to run them here:
https://asc.bmwgroup.net/wiki/display/APINEXT/Staging+Jobs+on+Zuul

### Staging jobs usage

The suggested usage of a staging job is to create your own branch and edit the [projects][1] file.
This will require most of these steps:

- Choose which [staging job][4] better suit your needs
- Place it on the 'test' pipeline
- Edit the configs you need (setup required vars):
  - In case you want to install some repo don't forget to add in the job vars 'install_build_tee: true'
- Commit changes
- Write 'retest' on the created PR conversation every time you want to trigger a new run

### Gerrit repos refspec install

By default no instalation will be done, hence using the ones coming in the image.
This is done by leaving the empty string, as set by default, on the repos refspec argument.
##### Example of usage to get the master version of the repo
```yaml
mtee_core_refspec: "refs/heads/master"
```
##### Example of usage of a specific refspec
```yaml
mtee_mgu22_refspec: "refs/changes/09/1756509/4"
```
Currently the list of gerrit repos able to be installed are:
```yaml
diagnose_refspec: refs/heads/master
dltlyse_refspec: refs/heads/master
lsmf_testing_refspec: refs/heads/master
mtee_core_refspec: refs/heads/master
mtee_gen22_refspec: refs/heads/master
mtee_mgu22_refspec: refs/heads/master
rsu_flasher_refspec: refs/heads/master
si_test_gen22_refspec: refs/heads/master
si_test_mgu22_refspec: refs/heads/master
sysman_testing_refspec: refs/heads/master
```
## Github repos

To run changes from these repos please use de common way to have dependencies on github
which is the 'depends-on:[url to repo's pr]' comment.
After this it's necessary to set to true the correspondent variable, which is false by default:
```yaml
install_si_test_apinext_in_staging: false
install_mtee_apinext_in_staging: false
```
After this the repos will be installed in the test environment, however only these are enabled:
[mtee-apinext][3]
[si-test-apinext][2]

## Define image

To define what image should be run there are two ways.

If you have a specific image to use, like a dirty or a specific release, please use the 'flashfiles_url' and the 'pdx_flashfiles_url', with the link to the 'images' and 'pdx' artifacts, respectivly.
The other way (which is the default), is to setup the variables that will be used to define what image should be used.
By default these are setup to run with the latest nightly.

## Example of 'flashfiles_url' and 'pdx_flashfiles_url'usage

```yaml
flashfiles_url: "https://apinext.artifactory.cc.bmwgroup.net/artifactory/apinext-nightly/22w29.5-1/bmw_idc23-mainline/userdebug/bmw_idc23-mainline-images_userdebug-22w29.5-1-nodex_IDC23_22w29.4-1-7.tar.gz"
pdx_flashfiles_url: "https://apinext.artifactory.cc.bmwgroup.net/artifactory/apinext-nightly/22w29.5-1/bmw_idc23-mainline/userdebug/bmw_idc23-mainline-pdx_userdebug-22w29.5-1-nodex_IDC23_22w29.4-1-7.tar.gz"
```

### IDC default:

```yaml
aosp_build_type_ta: 'userdebug' # options: 'production', 'user', 'userdebug'
branch_ta: mainline # options: 'mainline+latest-node0', 'stable'
nightly_pattern: "*/bmw_idc23-{{ branch_ta }}"
flashfiles_archive_pattern: "bmw_idc23-{{ branch_ta }}-images_{{ aosp_build_type_ta }}*.tar.gz"
```

### PADI default:

```yaml
aosp_build_type_ta: 'userdebug' # options: 'production', 'user', 'userdebug'
branch_ta: mainline # options: 'mainline+latest-node0', 'stable'
nightly_pattern: "*/bmw_rse22_padi-{{ branch_ta }}"
flashfiles_archive_pattern: "bmw_rse22_padi-{{ branch_ta }}-images_{{ aosp_build_type_ta }}*.tar.gz"
```

# Tests configurations

There are several possible configurations about what tests to run, what kind of flash, what test suit should be run and what dltlyse plugin
The staging base job is not ready to run any tests, so it requires at least some configuration
Two template jobs (for each ECU, IDC23 and RSE22) are available so the user can configure one with it's needs
If you want a pre-configured job the suggestion is to use 'ta-hw-mtf-idc23-flash-and-validate-SI-staging', which is already configured to flash target and run the test-suite SI, similar to ta-hw-mtf-idc23-flash-and-validate-SI

### staging base job

- idc23-flash-and-validate-staging

### android prod Si staging, runs apinext/si-test-apinext tests

- idc23-android-flash-and-prod-SI-staging

### prod Si staging, runs TEST_SUITE: SI

- ta-hw-mtf-idc23-flash-and-validate-SI-staging



**The suggested usage is to configure one of above jobs at your needs**



## Define flag to install build-tee artifacts (mandatory in case of installing some repo/refspec)

```yaml
install_build_tee: true
```

## Define test suite and test package

```yaml
job_environment:
  TEST_SUITE: SI-long
  TEST_PACKAGES: "!!si-test-mgu22/si_test_package_ecu_reboot"
```

## Define a metric collector

the default collector used is

```yaml
collector_type: "SI-android"
```

However another options can be found on '**COLLECT_TYPE_DICT**' at 'ascgit098.testing.reporting/metric_collector/program.py'

## Define a specific queue (ex. IDC Premium)

```yaml
mtf_config:
  queue: idc-premium_22_hu
```

## Define a dltlyse plugin list

the default variable to use is the:

```yaml
job_environment:
  DLTLYSE_PLUGIN_LIST: "BAT-dltlyse-plugins"
```

which receives a name of list to search for. Commonly these lists come from
"ascgit487.si-test-mgu22/test-suites"

However if a different list should be used (ex: defined on a github repo) then the variable '**custom_dltlyse_plugin**' should be used, which will overwrite the one from '**DLTLYSE_PLUGIN_LIST**'

```yaml
custom_dltlyse_plugin: "/opt/mtf3/workspace/current-task-workspace/home/zuul/src/cc-github.bmwgroup.net/apinext/si-test-apinext/dltlyse-plugins/apinext-idc-dltlyse-plugins"
```

## Define idc china target

```yaml
region_variant: china
```

## Run on a padi china

```yaml
mtf_config:
  queue: padi_22_china
```

## Adding LFS file to the Repo

Git LFS is enabled in the repo referring [Git LFS][5] and [PR][6]. When adding a new LFS file follow below steps:
- Follow steps 1-4, 7 and 8 in [Git LFS][5]
- While pushing the file git will ask for the username and password. Go to [user_profile][7] and Generate an Identity Token if not yet generated.
- Use the "Username" and "Reference Token" appearing in the dialog box as username & password. Save it for later use.
- Once generated the token is valid for 12 months.

## Creating testplan tickets for idc23 and padi jobs

NOTE: **Use with caution!!!!. Executing the script multiple times with same job name will create duplicate tickets for same job.**

Requires token for jira.cc.bmwgroup.net. 
Login to [CC-jira](https://jira.cc.bmwgroup.net/) > Profile > Personal Access Tokens > Create token

usage: python3 testplan.py --token TOKEN --target {idc23,padi} --jobs_file JOBS_FILE

testplan_config.yaml file will be created in yaml structure. You can copy and paste the data to reporting/xrayctl_configs/job_config.yaml

[1]: https://cc-github.bmwgroup.net/apinext/si-test-apinext/blob/master/zuul.d/projects.yaml
[2]: https://cc-github.bmwgroup.net/apinext/si-test-apinext
[3]: https://cc-github.bmwgroup.net/apinext/mtee-apinext
[4]: https://cc-github.bmwgroup.net/apinext/si-test-apinext/blob/master/zuul.d/jobs-staging.yaml
[5]: https://cc.bmwgroup.net/documentation/github/git-lfs.html
[6]: https://cc-github.bmwgroup.net/apinext/si-test-apinext/pull/913
[7]: https://apinext.artifactory.cc.bmwgroup.net/ui/user_profile