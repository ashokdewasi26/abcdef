import json
import logging
import re
import string
from pathlib import Path
from random import choice, randint

logger = logging.getLogger(__name__)


class MonkeyRunnerTest:
    """Monkey test runner to execute monkey test on target"""

    def __init__(self, test_target, monkey_script=None):
        """Init class

        :param test_target: TestBase instance to handle the apinext target
        :param monkey_script: Given script to be executed otherwise auto generated one will be executed,
                            defaults to None
        """
        self._target = test_target
        self._package_to_test = ""
        self._seed = ""
        self._nr_interactions = 200
        self._verbosity = 3
        self._throttle = 100  # Milliseconds
        self.monkey_script = monkey_script

    def start_monkey_test(self, timeout=3000, monkey_test_name=None):
        _cmd = ""
        if self.monkey_script:
            self.monkey_script = Path(self.monkey_script)
            logger.info(f"Monkey will try to run script file: '{str(self.monkey_script)}' with timeout: {timeout}")
            assert self.monkey_script.is_file(), f"Monkey script file not found {str(self.monkey_script)}"

            self._target.apinext_target.push_as_current_user(self.monkey_script, "/sdcard/monkey.script")
            self._seed = ""
            self._package_to_test = ""

        if len(self._seed) > 1 and self._seed.isnumeric():
            _cmd += "-s %s" % self._seed

        if len(self._package_to_test) > 1:
            _cmd += " -p %s" % self._package_to_test

        if self._verbosity > 3 or self._verbosity < 1:
            self._verbosity = 3

        _cmd += " -c android.intent.category.LAUNCHER "
        _cmd += "--pct-syskeys 0 "
        _cmd += "-v " * self._verbosity
        _cmd += f"--throttle {self._throttle} "

        if self.monkey_script:
            _cmd += "-f /sdcard/monkey.script 1"
        else:
            _cmd += str(self._nr_interactions)

        log_file_name = f"/sdcard/monkey_stress_{monkey_test_name}.log"
        _cmd += f" > {log_file_name} 2>&1"  # 2>&1 append stderr to stdout
        logger.info(f"Monkey cmd used {_cmd}")
        try:
            self._target.apinext_target.execute_command(
                cmd=[
                    "monkey",
                    "--ignore-timeouts --ignore-security-exceptions",
                    f" --kill-process-after-error --monitor-native-crashes {_cmd}",
                ],
                timeout=timeout,
            )
            self._target.apinext_target.pull(src=log_file_name, dest=self._target.results_dir, timeout=60)
        except Exception as error:
            raise Exception(f"The following error occurred while performing the monkey test:{error}")


class AvailableInputs:
    """
    Create methods capable to be recognized by monkey tool
    """

    KEY_ACTION_DOWN = 0
    KEYCODE_ZOOM_OUT = 168
    x_exclude = (2060, 2160)
    y_exclude = (50, 175)

    def __init__(self, test_target):
        self._target = test_target
        self.x_size, self.y_size = self.get_window_size(self._target.apinext_target)
        logger.debug(f"x_size = {self.x_size} | y_size = {self.y_size}")

    def get_window_size(self, target):
        size = target.execute_adb_command(["shell", "wm size"])
        size = size.split(" ")[-1]
        x_box, y_box = size.split("x")
        x_box = int(x_box)
        y_box = int(y_box)
        return x_box, y_box

    def generate_coordinates(self, x_min=0, x_max=None, y_min=0, y_max=None):
        """
        Exclude regions on the screen which turns off the display.
        :param x_min: Min x coordinate
        :param x_max: Max x coordinate, if is not passed as an argument it will take on the value of the x_size
        :param y_min: Min y coordinate
        :param y_max: Max y coordinate, if is not passed as an argument it will take on the value of the y_size
        :return: A valid pixel(int)
        """

        if x_max is None:
            x_max = self.x_size

        if y_max is None:
            y_max = self.y_size

        while True:
            x = randint(x_min, x_max)
            y = randint(y_min, y_max)
            if x < self.x_exclude[0] or x > self.x_exclude[1] or y < self.y_exclude[0] or y > self.y_exclude[1]:
                logger.debug(f"Generated the following coordinates: x = {x}, y = {y}")
                return x, y

    def tap(self):
        """
        Tap(x, y, tapDuration)：Simulate a finger Click the event.
        Parameters: x, y is the control coordinates, TAPDuration is the duration of the clicks, which can be omitted.
        """
        x, y = self.generate_coordinates()
        duration = randint(1, 5)
        return f"Tap({x},{y},{duration})"

    def dispatch_press(self):
        """
        DispatchPress(keyName)：Button. Parameters: Keycode.
        Detailed Android Keycode list: https://developer.android.com/reference/android/view/KeyEvent
        """
        key_name = randint(self.KEY_ACTION_DOWN, self.KEYCODE_ZOOM_OUT)
        return f"DispatchPress({key_name})"

    def press_and_hold(self):
        """
        PressAndHold(x, y, pressDuration)： Simulated long press events.
        x, y is the control coordinates, pressDuration is the duration of the clicks, which can be omitted.
        """
        x, y = self.generate_coordinates()
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
        x_start, y_start = self.generate_coordinates()
        x_stop, y_stop = self.generate_coordinates()
        step_count = randint(1, 5)
        return f"Drag({x_start}, {y_start}, {x_stop}, {y_stop}, {step_count})"

    # def rotate_screen(self):
    #     """
    #     RotateScreen(rotationDegree, persist)：Rotate the screen. Parameters: rotationdegree is a rotation angle,
    #         E.G. 1 represents 90 degrees; PERSIST indicates whether it is fixed after the rotation,
    #         and 0 indicates that the rotation is restored, and non-0 means fixed constant.
    #     """
    #     rotation = randint(1, 4)
    #     persist = randint(0, 1)
    #     return f"RotateScreen({rotation}, {persist})"

    # def dispatch_flip(self):  # Function disable on IDCEvo
    #     """DispatchFlip(true/false)：Turn the soft keyboard on or off."""
    #     random = randint(0, 1)
    #     random = True if random == 1 else False
    #     return f"DispatchFlip({random})"

    def long_press(self):
        """LongPress()：Long press 2 seconds."""
        return "LongPress()"

    def user_wait(self):
        """UserWait(sleepTime)：Sleep between 1 to 2 seconds"""
        sleep = randint(1, 2)

        # Time measurement in milliseconds
        sleep = sleep * 1000
        return f"UserWait({sleep})"

    # def device_wake_up(self):  # Function not suitable for IDCEvo, since we are assuring the system is never at sleep
    #     """DeviceWakeUp()：Wake up screen."""
    #     return "DeviceWakeUp()"

    def pinch_zoom(self):
        """
        PinchZoom(x1Start, y1Start, x1End, y1End, x2Start, y2Start, x2End, y2End, stepCount)：Analog zoom gestures.
        """
        zoom = round(self.y_size * 0.2)
        x1 = randint(round(self.x_size * 0.2), round(self.x_size * 0.8))
        y1 = randint(round(self.y_size * 0.2), round(self.y_size * 0.8))
        x2 = randint(round(self.x_size * 0.2), round(self.x_size * 0.8))
        y2 = randint(round(self.y_size * 0.2), round(self.y_size * 0.8))

        return f"PinchZoom({x1}, {y1}, {x1-zoom}, {y1-zoom}, {x2}, {y2}, {x2+zoom}, {y2+zoom}, {zoom})"


class CreateMonkeyFile:
    """
    Create Monkey files:
        * Script for testing
        * Package List to update current scripts
    """

    header = "type= raw events\ncount= {}\nspeed= 1.0\nstart data >>"
    launch_activity = "LaunchActivity({}, {})"

    list_test = []

    def __init__(self, test_target, ref_files):
        self._target = test_target
        self.ref_files = ref_files

        self.monkey_script_name = Path(Path(self._target.results_dir) / "new_monkey.script")
        self.monkey_packages_name = Path(Path(self._target.results_dir) / "new_monkey_packages.json")
        self.monkey_script_fixed_actions_name = Path(Path(self._target.results_dir) / "fixed_actions_monkey.script")

        self.get_package_activities()
        inputs_available = AvailableInputs(self._target)
        self.inputs = [
            inputs_available.dispatch_string,
            inputs_available.press_and_hold,
            inputs_available.tap,
            inputs_available.dispatch_press,
            inputs_available.drag,
            inputs_available.pinch_zoom,
            inputs_available.long_press,
            inputs_available.user_wait,
        ]

    def get_package_activities(self, write_to_file=True):
        """
        Launch monkey activity to collect all packages and activity with class android.intent.category.LAUNCHER

        Output:
            * List packages available on target and save it to {monkey_packages_name}
        """
        monkey_file = self._target.apinext_target.execute_command(
            ["monkey", "-c android.intent.category.LAUNCHER --pct-syskeys 0 -v -v -v 0"]
        )
        pattern = re.compile(r"Using main activity\s(?P<activity>\S*).*from package\s(?P<package>[\w.]*)")
        monkey_lines = monkey_file.split("\n")
        for line in monkey_lines:
            match = pattern.search(line)
            if match:
                match_dict = match.groupdict()
                if "appium" not in match_dict.get("package"):
                    self.list_test.append([match_dict.get("package"), match_dict.get("activity")])
        # Order list alphabetically
        self.list_test.sort(key=lambda x: x[0])
        if write_to_file:
            with open(self.monkey_packages_name, "w") as outfile:
                json.dump(self.list_test, outfile)

    def write_to_file(self, nr_iterations):
        """
        Write a new monkey.script file in case there is packages which must be tested and are not deployed yet.

        This files contain a start activity and random nr_iterations for each package in self.list_test.

        nr_iterations - int: Number of interaction produced by monkey for each package

        Output:
            * monkey script callable with name: {monkey_script_name}
        """
        with open(self.monkey_script_name, "w") as outfile:
            outfile.write(self.header.format(len(self.list_test) * nr_iterations) + "\n")
            for package in self.list_test:
                outfile.write(self.launch_activity.format(package[0], package[1]) + "\n")
                for _ in range(0, nr_iterations):
                    outfile.write(choice(self.inputs)() + "\n")

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

    def create_new_script_with_fixed_actions(self, actions_file):
        """
        Generate a script for all the packages but with a fixed set of actions between activities

        Output:
            * New monkey script callable with name: {monkey_script_fixed_actions_name}

        """
        with open(actions_file, "r") as file:
            fixed_actions_set = file.read()

        with open(self.monkey_script_fixed_actions_name, "w") as outfile:
            outfile.write(self.header.format(len(self.list_test)) + "\n")
            for package in self.list_test:
                outfile.write(self.launch_activity.format(package[0], package[1]) + "\n")
                outfile.write(fixed_actions_set + "\n")
