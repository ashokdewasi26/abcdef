# Stress Test

## Monkey test variables

### monkey_package

Specify one or more packages

### monkey_seed

Specify seed value for pseudo-random number generator

### monkey_verbosity

Specify log level. Default is 3

### monkey_interaction

Specify fixed delay between events. Default is 500

### monkey_test_extra_args

Specify extra args for monkey test, For more detail, Please refer
to [monkey](https://developer.android.com/studio/test/monkey),
[MonkeyRunner](https://developer.android.com/studio/test/monkeyrunner/MonkeyRunner)
and [Monkey-script](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_package_a_monkey/systemtests/ref_files/monkey.script)

### monkey_save_log

Specify whether export log to test-artifacts. Default is true

### monkey_record_video

Specify whether need record video during monkey test. Default is true


## Monkey scripting

Sometimes we don't want it to run randomly and the test can be done according to our configured process using scripts. Use the -f parameter to run the Monkey: adb shell monkey script -f <`script`> 1.

The official site does not use the Monkey script articles, you can refer to the writing in the SDK source code [MonkeySourceScript.java](https://android.googlesource.com/platform/development/+/master/cmds/monkey/src/com/android/commands/monkey/MonkeySourceScript.java). You can refer to this class.

The basic commands of the Monkey script:

- DispatchPointer(idle time, eventTime, action, x, y, xpressure, size, metastate, xPrecision, yPrecision, device, edgeFlags): A gesture operation equivalent to pressing a finger to a specific position.The x, y parameters are the coordinates of the position of the finger pressed, position coordinates can be obtained with the UI Automator tool in DDMS, and the position is in sdk / tools / monitor.
- DispatchPress(keycode): Press a fixed system key such as the home button, back button, etc. There is a detailed introduction to the meaning of each keycode in this class on the officialKeuEvent website.
- LaunchActivity(pkg_name, cl_name): Used to launch the application. Parameters: package name + class name.
- UserWait(sleepTime): Let the script pause for a while
- RotateScreen(rotationDegree, persist): rotationDegree - rotation angle + need to stop at current position after rotation. 0 means 0 degrees 1 means 90 degrees 2 means 180 degrees 3 means 270 degrees; persist - 0 means recovery after rotation, nonzero value means fixed
- Tap(x, y, tapDuration): Tap screen coordinate
- Drag(xStart, yStart, xEnd, yEnd): The parameter for sliding across the screen is the start point of the sliding coordinates
- LongPress(): Long press for 2 seconds
- ProfileWait(): Wait for 5 seconds
- PressAndHold(x, y, pressDuration): Simulate a long press
- PinchZoom(x1Start, y1Start, x1End, y1End, x2Start, y2Start, x2End, y2End, stepCount): Analog scaling
- DispatchString(input): Input string
- RunCmd(cmd): Execute shell commands such as screencap -p /data/temp/temp.png
- DispatchFlip(true / false): Open or close the soft keyboard
- DeviceWakeUp(): Bring screen out of sleep mode
