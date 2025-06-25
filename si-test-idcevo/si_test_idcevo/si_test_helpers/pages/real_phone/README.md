# TRAAS with Real Phone

## Introduction
With the goal of increasing the coverage of our tests, we attached a smartphone to one of our test racks (CTW_CR_006_NA05), via usb cable. The smartphone is directly connected to the Host PC on the testrack, which detects it as a connected adb device. This gives us the possibility to interact with the smartphone via Appium, and therefore develop automated tests which interact both with the IDCEvo and the phone. Example: Bluetooth testing.

In this documentation we detail the process of connecting the phone to the worker and interacting with it through automated tests.

## Important
After having more than one android device connected all the adb commands need to specify the device the command is meant to. This means all adb commands need to have the ‘-s’ option with followed by the android serial specified.  (<https://developer.android.com/studio/command-line/adb#directingcommands>)

Steps:

1. ### Phone preparation steps

   1. Enable developer options on the phone (see https://developer.android.com/studio/debug/dev-options#enable)
   2. Enable USB debugging setting (see https://developer.android.com/studio/debug/dev-options#Enable-debugging)
   3. Allow app install via USB setting
   4. Deactivate automatic adb revoke after 7 days

2. ### Setup phone-worker connection

   1. Plug the phone to the worker via USB
   2. Access worker user ‘tu\_bci\_unix’
   3. Send ‘adb devices’ command (which will make sure adb server is running). The response of the command should be a list of connected devices, where the phone android serial number should appear followed by ‘unauthorized’
   4. On the phone, there should be a pop up with an adb debug request, accept it with the option ‘always allow this user’
   5. Again send ‘adb devices’ command and validate the phone android serial number is now followed by ‘device’ and not ‘unauthorized’, meaning the phone is correctly connected.

3. ### TRAAS framework adaptations

   1. As previously mentioned, with having more than one android device connected, we need to pass the android serial number in every adb command, so it knows the device it’s destinated. To do this we updated the worker configuration to make sure the android serials of the HU, the phone and any other android device connected to the worker are defined on the ‘nosetests’ section of the file: “/home/tu\_bci\_unix/mtee-hu.cfg”
      1. Currently the naming used was:

      ###### hu-android-serial=XXXXX

      ###### ext-real-phone-android-serial=XXXXX

   2. At each new TRAAS session all the necessary dockers are brought up, and so a new authorization on the phone would be needed for these dockers to be able to interact with it. To avoid having to do this in every new session, we can copy the session's adb keys from user ‘tu\_bci\_unix’ (during phone-worker connection setup) to the .android directory of the host PC. These adb keys are then shared with traas-deploy so the device will be available in every new TRAAS session, without additional authorizations/actions needed.

   To do this, start a new TRAAS session and connect to the Host PC via ssh. Then you'll have to copy the adb files present in the session's path '/home/tu\_bci\_unix/.android' to the same path in the Host PC.

4. Usage – Phone as an Android device (si-test-idcevo scope)

   1. A class ‘RealPhoneTarget’ was created, which inherits from ‘AndroidTarget’
   https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/create_first_idcevo_phone_test/si_test_idcevo/si_test_helpers/android_testing/real_phone_target.py
   2. The goal is to re-use the already existing methods for Android/adb in mtee-apinext
   3. To setup this handler we need to instantiate it by passing the Real Phone android serial number
   4. This class is currently used to group some hardware specific methods based on adb related with unlock screen and turn on Bluetooth

5. Usage – Phone with Appium session (si-test-idcevo scope)

   1. A class ‘RealPhoneAppiumTarget was created, which inherits from ‘RealPhoneTarget’
   https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/create_first_idcevo_phone_test/si_test_idcevo/si_test_helpers/android_testing/real_phone_appium_target.py
   2. The goal is to group methods related with Appium session and driver
   3. This class needs to be instantiated with the Real Phone android serial number and also a ‘system port’ (different than the default one) to be used by Appium to open a new driver (meaning two different Appium sessions will be running at the same time). An example: https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/d5f25c36ef295b92e2e29dcdee4c440431c2b889/si_test_idcevo/si_test_package_real_phone/systemtests/real_phone_tests.py#L35-L41
   4. Useful info/links:
      1. <https://appium.io/docs/en/advanced-concepts/parallel-tests/>
      2. <https://github.com/appium/appium-uiautomator2-driver#driverserver>
