# TRAAS with Real Phone

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

   2. At each new TRAAS session all the necessary dockers are brought up, and so a new authorization on the phone would be needed for these dockers to be able to interact with it. To avoid this, we use the already authorized adb keys from user ‘tu\_bci\_unix’ (during phone-worker connection setup). These adb keys are shared with traas-deploy so the device is available during the TRAAS session and no additional authorization/action is needed.

      1. Patch to do this during ‘start\_service\_sync.sh’:

      https://asc.bmwgroup.net/gerrit/#/c/1985924

4. Usage – Phone as an Android device (si-test-apinext scope)

   1. A class ‘RealPhoneTarget’ was created, which inherits from ‘AndroidTarget’
   https://cc-github.bmwgroup.net/apinext/si-test-apinext/blob/master/si_test_apinext/testing/real_phone_target.py
   2. The goal is to re-use the already existing methods for Android/adb in mtee-apinext
   3. To setup this handler we need to instantiate it by passing the Real Phone android serial number
   4. This class is currently used to group some hardware specific methods based on adb related with unlock screen and turn on Bluetooth

5. Usage – Phone with Appium session (si-test-apinext scope)

   1. A class ‘RealPhoneAppiumTarget was created, which inherits from ‘RealPhoneTarget’
   https://cc-github.bmwgroup.net/apinext/si-test-apinext/blob/master/si_test_apinext/testing/real_phone_appium_target.py
   2. The goal is to group methods related with Appium session and driver
   3. This class needs to be instantiated with the Real Phone android serial number and also a ‘system port’ (different than the default one) to be used by Appium to open a new driver (meaning two different Appium sessions will be running at the same time). An example: https://cc-github.bmwgroup.net/apinext/si-test-apinext/blob/cc2f67f1284b66583a2e832b84e3779e6d09e326/si_test_apinext/real_phone/real_phone_tests.py#L38-L45
   4. Useful info/links:
      1. <https://appium.io/docs/en/advanced-concepts/parallel-tests/>
      2. <https://github.com/appium/appium-uiautomator2-driver#driverserver>

