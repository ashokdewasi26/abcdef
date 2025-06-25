# Stress Test

## Monkey Test variables

### monkey_package

Specify one or more packages

### monkey_seed

Specify Seed value for pseudo-random number generator

### monkey_verbosity

Specify log level. Default is 3

### monkey_interaction

Specify fixed delay between events. Default is 500

### monkey_test_extra_args

Specify extra args for monkey test, For more detail, Please refer
to [monkey](https://developer.android.com/studio/test/monkey),
[MonkeyRunner](https://developer.android.com/studio/test/monkeyrunner/MonkeyRunner)
and [Monkey-script](https://blog.katastros.com/a?ID=01150-a891da6c-b3cc-4196-89a0-2dad765495ad)

### monkey_save_log

Specify whether export log to test-artifacts. Default is true

### monkey_record_video

Specify whether need record video during monkey test. Default is true


# **_Monkey scripting._**

Sometimes we don't want it to run randomly and the test can be done according to our configured process using scripts. Use the -f parameter to run the Monkeyadb shell monkey script -f <`script`> 1. 

The official site does not use the Monkey script articles, you can refer to the writing in the SDK source code. [MonkeySourceScript.java](https://android.googlesource.com/platform/development/+/master/cmds/monkey/src/com/android/commands/monkey/MonkeySourceScript.java) You can refer to this class.

The basic commands of the Monkey script:

    DispatchPointer (idle time, eventTime, action, x, y, xpressure, size, metastate, xPrecision, yPrecision, device, edgeFlags): a gesture operation equivalent to pressing a finger to a specific position.The x, y parameters are the coordinates of the position of the finger pressed, position coordinates can be obtained with the UI Automator tool in DDMS, and the position is in sdk / tools / monitor.
    DispatchPress [keycode] Press a fixed system key such as the home button, back button, etc. There is a detailed introduction to the meaning of each keycode in this class on the officialKeuEvent website.
    LaunchActivity (pkg_name, cl_name): used to launch the application. Parameters: package name + class name.
    UserWait: let the script pause for a while
    UserWait (sleepTime): specify sleep time
    RotateScreen (rotationDegree, persist): parameter - rotation angle + need to stop at current position after rotation. 0 means 0 degrees 1 means 90 degrees 2 means 180 degrees 3 means 270 degrees; the second parameter 0 means recovery after rotation, nonzero value means fixed
    Tap (x, y, tapDuration): click time x y - tap screen coordinate
    Drag (xStart, yStart, xEnd, yEnd): the parameter for sliding across the screen is the start point of the sliding coordinates
    LongPress (): long press for 2 seconds
    ProfileWait (): wait for 5 seconds
    PressAndHold (x, y, pressDuration): simulate a long press
    PinchZoom (x1Start, y1Start, x1End, y1End, x2Start, y2Start, x2End, y2End, stepCount): analog scaling
    DispatchString (input): input string
    RunCmd (cmd): execute shell commands such as screencap -p /data/temp/temp.png
    DispatchFlip (true / false): Open or close the soft keyboard
    DeviceWakeUp (): bring screen out of sleep mode