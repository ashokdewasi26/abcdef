#!/bin/bash

#   Script for setting up local variables and execute SI Tests
# Needs to be executed inside si-test-apinext folder and
# test-automation repo needs to be installed.
#   If no argument passed, it will execute all test inside si_tests folder
# however, if some folder passed as argument, it only execute test inside
# that folder

export ANDROID_HOME=~/Android/Sdk
export PRODUCT_TYPE=idc23_b2
export PATH=~/Android/Sdk/platform-tools:$PATH
export TA_SRC_DIR=~/Projects/codecraft/test-automation/
export REGION_VARIANT=row

rm -r results/

# TODO: add --with-post-tests option
if [[ $# -eq 0 ]] ;
then

    mkdir -p results
    found_tests=$(mktemp -p ./results --suffix _found_tests)

    find si_test_apinext/si_tests/ -type f -name "test*.py" -exec echo -n "{} " \; | sort -z > "${found_tests}"

    cat "${found_tests}"

    # shellcheck disable=SC2046
    ../test-automation/ta.sh run-tests $(cat "${found_tests}")

else

    echo "$(tput setaf 1) Execute tests on { $1 } Directory"
    ../test-automation/ta.sh run-tests "$1"

fi
