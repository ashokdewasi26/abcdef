# How trigger and extract full RAM dump

This page intends to explain how to trigger a full RAM dump on BAT test setup in this case on a SI job.
First we should go through how to manually do it.

## Manual steps for RAM dump

Open a serial connection to IDCevo ECU.
On the console, send the input to a ipc channel requiring ramdump mode on the next lifecycle and next trigger a kernel panic:
```shell
echo -e -n '\x01\x00\x00\x10\x00\x01' > /dev/ipc12
echo 1 > /sys/nk/prop/nk.panic-trigger
```

After this the target will reboot and enter into fastboot ramdump mode. You can follow the serial output and target should stop here: 

```text
08:21:56,113174 fastboot is now in ramdump mode!!
08:21:56,114272 This is do_fastboot
08:21:56,114907 fastboot_init success!!
08:21:56,115265 PHY Boot mode :ROM mode start
08:21:56,128666 SUP_DIG_IDCODE_LO:0x54cd
08:21:56,129200 [Current] SUP_DIG_LVL_OVRD_IN:0x0055
08:21:56,129570 [Modified] SUP_DIG_LVL_OVRD_IN:0x00f5
08:21:56,672780 enumeration success
```

Once the target is in this state we will need to run the harman script to extract the ramdump from the target.

This script is available on 2 locations, choose the one is best for you:

- image/build, available on: images\idcevo-hv\idcevo\ramdump\dumptool
- github repo: idcevo/harman-ramdump-tool: Repository requested by harman


You need to have python3 to run the script.
If you are on windows make sure you have the "dumptool\bin\fastboot-eauto.exe" with permissions to be executed or if you are on linux the "dumptool\bin\fastboot-eauto"

Then you want to execute the following command inside dumptool folder:
```shell
python3 eautodump.py -m all
```
- "-t <path>"  -> specify the folder you want the ramdump to go otherwise a new folder will be created on the same folder you executed the script, which should be inside dumptool folder.

Wait for script to end and that' it. This will dump around **17 gigabytes** of data, make sure you have room for that.



After the script finished target should stop on the same state as mention before with fastboot ramdump mode and stating "enumeration success".

You can give 'ctrl+c' input to exit fastboot and go into LK shell, then type 'boot' and system will reboot or simply trigger a power cycle to reboot the target.



## Automated way using test-farm setup

There is a simple test on our repo which provides a small demonstration on how to do it. [full_ramdump_tests.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/tree/master/si_test_idcevo/si_test_package_system_software/systemtests/full_ramdump_tests.py)

To run this test, you need to add it to the [SI-staging-systemtests-idcevo](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/tree/master/test-suites/idcevo/SI-staging-systemtests-idcevo)

You can leave the other tests, like:

```text
si-test-idcevo/si_test_package_basic
si-test-idcevo/si_test_package_common
si-test-idcevo/si_test_package_system_software/systemtests/full_ramdump_tests.py
```

In our PR after this change you only need to write retest and it will run a RAM dump.

**Feel free to change the actions done before the RAM dump**


## Intensive Reboot testing searching for CPU 'fail to boot'

For the record this wiki and the RAM dump topic came from this ticket:
[Defect ticket](https://jira.cc.bmwgroup.net/browse/IDCEVODEV-355354)

Which then derived into a special request for our team to setup this full ramdump and try to reproduce the issue.
[lion internal task](https://jira.cc.bmwgroup.net/browse/IDCEVODEV-384913)

I created a PR that performs many reboot cycles and if a cpu fails to boot or is offline we trigger a RAM dump
[intensive rebooting PR](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/pull/1575)