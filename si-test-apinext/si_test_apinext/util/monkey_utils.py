import json
import logging
from pathlib import Path
from random import choice, randint
import re
import string

import si_test_apinext.util.driver_utils as utils

logger = logging.getLogger(__name__)


class MonkeyRunnerTest:
    def __init__(self, test_target, ref_files):
        """"""
        self._target = test_target
        self._package_to_test = ""
        self._seed = ""
        self._nr_interactions = 5000
        self._verbosity = 3
        self._save_log = True
        self._record_video = True
        self._use_script = True
        self._throttle = 100  # Milliseconds
        self._ref_files = ref_files

    def start_monkey_test(self):
        _cmd = ""
        video_record_started = False
        if self._use_script:
            monkey_script = (
                Path(self._ref_files) / "monkey.script"
                if "new_monkey.script" not in str(self._ref_files)
                else self._ref_files
            )
            logger.info(f"Monkey will run script file: '{monkey_script}'")
            assert monkey_script.is_file()
            self._target.apinext_target.push_as_current_user(monkey_script, "/sdcard/monkey.script")
            self._seed = ""
            self._package_to_test = ""

        if self._record_video:
            utils.start_recording(self._target)
            video_record_started = True

        if len(self._seed) > 1 and self._seed.isnumeric():
            _cmd += "-s %s" % self._seed

        if len(self._package_to_test) > 1:
            _cmd += " -p %s" % self._package_to_test

        if self._verbosity > 3 or self._verbosity < 1:
            self._verbosity = 3

        _cmd += " -c android.intent.category.LAUNCHER "
        _cmd += "-v " * self._verbosity
        _cmd += f"--throttle {self._throttle} "

        if self._use_script:
            _cmd += "-f /sdcard/monkey.script 1"
        else:
            _cmd += str(self._nr_interactions)

        if self._save_log:
            _cmd += " > /sdcard/monkey_stress.log 2>&1"

        logger.info(f"Monkey cmd used {_cmd}")
        self._target.apinext_target.execute_adb_command(
            cmd=[
                "shell",
                "monkey",
                "--ignore-timeouts --ignore-security-exceptions"
                f" --kill-process-after-error --monitor-native-crashes {_cmd}",
            ],
            timeout=1000000,
        )
        if video_record_started:
            video_name = "monkey_stress_" + self._package_to_test
            utils.stop_recording(self._target, video_name)
        if self._save_log:
            self._target.apinext_target.pull(
                src="/sdcard/monkey_stress.log", dest=self._target.results_dir, timeout=60
            )


class AvailableInputs:
    """
    Create methods capable to be recognized by monkey tool
    """

    KEYCODE_SOFT_LEFT = 1
    KEYCODE_ZOOM_OUT = 169
    x_exclude = (1630, 1800)
    y_exclude = (50, 300)

    def __init__(self, test_target):
        self._target = test_target
        self.x_size, self.y_size = self.get_window_size(self._target.apinext_target)

    def get_window_size(self, target):
        size = target.execute_adb_command(["shell", "wm size"])
        size = size.split(" ")[-1]
        x_box, y_box = size.split("x")
        x_box = int(x_box)
        y_box = int(y_box)
        return x_box, y_box

    def generate_random(self, max_pixel_val, exlude_range):
        """
        Exclude regions on the screen which turns off the display.

        :param max_pixel_val: Max pixel size of screen(width/height)
        :param exlude_range: Tuple of min and max value of range to neglect
        :return: A valid pixel(int)
        """
        while True:
            pixel = randint(0, max_pixel_val)
            if pixel < exlude_range[0] or pixel > exlude_range[1]:
                return pixel

    def tap(self):
        """
        Tap(x, y, tapDuration)：Simulate a finger Click the event.
        Parameters: x, y is the control coordinates, TAPDuration is the duration of the clicks, which can be omitted.
        """
        x = self.generate_random(self.x_size, self.x_exclude)
        y = self.generate_random(self.y_size, self.y_exclude)
        duration = randint(1, 5)
        return f"Tap({x},{y},{duration})"

    def dispatch_press(self):
        """
        DispatchPress(keyName)：Button. Parameters: Keycode.
        Detailed Android Keycode list: https://developer.android.com/reference/android/view/KeyEvent
        """
        while True:
            key_name = randint(self.KEYCODE_SOFT_LEFT, self.KEYCODE_ZOOM_OUT)
            if key_name != 26:  # Neglect keycode power
                return f"DispatchPress({key_name})"

    def press_and_hold(self):
        """
        PressAndHold(x, y, pressDuration)： Simulated long press events.
        x, y is the control coordinates, pressDuration is the duration of the clicks, which can be omitted.
        """
        x = self.generate_random(self.x_size, self.x_exclude)
        y = self.generate_random(self.y_size, self.y_exclude)
        duration = randint(1, 5)
        return f"PressAndHold({x}, {y}, {duration})"

    def dispatch_string(self):
        """DispatchString(input)：Enter a string."""
        length = randint(1, 7)
        letters = string.ascii_letters
        string_send = "".join(choice(letters) for i in range(length))
        return f"DispatchString({string_send})"

    def drag(self):
        """Drag(xStart, yStart, xEnd, yEnd, stepCount)：Used to simulate a drag operation."""
        x_start = randint(0, self.x_size)
        y_start = randint(0, self.y_size)
        x_stop = randint(0, self.x_size)
        y_stop = randint(0, self.y_size)
        step_count = randint(1, 5)
        return f"Drag({x_start}, {y_start}, {x_stop}, {y_stop}, {step_count})"

    def new_monkey_intents(self):

        # https://www.programmerall.com/article/14481822934/

        # LaunchActivity(pkg_name, cl_name)：Launch the application of the application of Activity.
        # Parameters: package name and started Activity.

        # RotateScreen(rotationDegree, persist)：Rotate the screen. Parameters: rotationdegree is a rotation angle,
        #   E.G. 1 represents 90 degrees; PERSIST indicates whether it is fixed after the rotation,
        #   and 0 indicates that the rotation is restored, and non-0 means fixed constant.

        # DispatchFlip(true/false)：Turn the soft keyboard on or off.

        # LongPress()：Long press 2 seconds.

        # PinchZoom(x1Start, y1Start, x1End, y1End, x2Start, y2Start, x2End, y2End, stepCount)：Analog zoom gestures.

        # UserWait(sleepTime)：Sleep for a while

        # DeviceWakeUp()：Wake up screen.

        # PowerLog(power_log_type, test_case_status)：Analog battery power information.

        # WriteLog()：Write the battery information to the SD card.

        # RunCmd(cmd)：Run the shell command.

        # DispatchPointer(downtime,eventTime,action,x,yxpressure,size,metastate,xPrecision,yPrecision,device,edgeFlags)：
        # Send a single gesture to the specified location.

        # DispatchPointer(downtime,eventTime,action,x,yxpressure,size,metastate,xPrecision,yPrecision,device,edgeFilags)：
        # Send a button message.

        # LaunchInstrumentation(test_name,runner_name): Run an Instrumentation test case.

        # DispatchTrackball：Analog transmit track traces.

        # ProfileWait：Wait for 5 seconds.

        # StartCaptureFramerate()：Get the frame rate.

        # EndCaptureFramerate(input): End the acquisition frame rate.
        pass


class CreateMonkeyFile:
    """
    Create Monkey files:
        * Script for testing
        * Package List to update current scripts
    """

    header = "type= raw events\ncount= {}\nspeed= 1.0\nstart data >>"
    launch_activity = "LaunchActivity({}, {})"
    whitelist_packages = ["appium", "deskclock", "dummyapp"]

    list_test = []

    def __init__(self, test_target, ref_files):
        self._target = test_target
        self.ref_files = ref_files

        self.monkey_script_name = Path(Path(self._target.results_dir) / "new_monkey.script")
        self.monkey_packages_name = Path(Path(self._target.results_dir) / "new_monkey_packages.json")

        self.get_package_activities()
        inputs_available = AvailableInputs(self._target)
        self.inputs = [
            inputs_available.dispatch_string,
            inputs_available.press_and_hold,
            inputs_available.tap,
            inputs_available.dispatch_press,
            inputs_available.drag,
        ]

    def get_package_activities(self):
        """
        Launch monkey activity to collect all packages and activity with class android.intent.category.LAUNCHER

        Output:
            * List packages available on target
        """
        monkey_file = self._target.apinext_target.execute_adb_command(
            ["shell", "monkey", "-c android.intent.category.LAUNCHER -v -v -v 0"]
        )
        pattern = re.compile(r"Using main activity\s(?P<activity>\S*).*from package\s(?P<package>[\w.]*)")
        monkey_lines = monkey_file.split("\n")
        for line in monkey_lines:
            match = pattern.search(line)
            if match:
                match_dict = match.groupdict()
                package = match_dict.get("package")
                activity = match_dict.get("activity")
                if not any(each_package in package for each_package in self.whitelist_packages):
                    self.list_test.append([package, activity])

    def write_to_file(self, nr_iterations):
        """
        Write a new monkey.script file in case there is packages which must be tested and are not deployed yet.

        This files contain a start activity and random nr_iterations for each package in self.list_test.

        nr_iterations - int: Number of interaction produced by monkey for each package

        Output:
            * monkey script callable with name: {monkey_script_name}
            * monkey packages tested: {monkey_packages_name}
        """
        with open(self.monkey_script_name, "w") as outfile:
            outfile.write(self.header.format(len(self.list_test) * nr_iterations) + "\n")
            for package in self.list_test:
                outfile.write(self.launch_activity.format(package[0], package[1]) + "\n")
                for _ in range(0, nr_iterations):
                    outfile.write(choice(self.inputs)() + "\n")

        with open(self.monkey_packages_name, "w") as outfile:
            json.dump(self.list_test, outfile)

    def validate_packages(self):
        """
        Get package from target, get_Package_Activities method, and compare it with current package list

        Output:
            * Package which are not tested and packages which are no longer into target.

        """
        filename = Path(self.ref_files / "monkey_packages.json")
        error_list = []
        packages_not_tested = ""
        packages_new = ""
        aux_list = self.list_test[:]
        with open(filename) as json_file:
            data = json.load(json_file)
            for package_tested in data:
                if package_tested not in aux_list:
                    packages_not_tested += str(package_tested)
                else:
                    aux_list.remove(package_tested)

        if packages_not_tested:
            error_list.append(f"Package(s) not tested because don't exist in current image: {package_tested}")
        if any(aux_list):
            for package_new in aux_list:
                packages_new += str(package_new)
            error_list.append(
                f"Packages present on current image but NOT TESTED (maybe add them to list): {packages_new}"
            )

        return error_list
