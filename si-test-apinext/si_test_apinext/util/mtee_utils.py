from datetime import datetime
import logging
import re
import os
import shutil
import time
from typing import Optional

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_equal
import si_test_apinext.util.driver_utils as utils
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions


lifecycle_tools = LifecycleFunctions()
logger = logging.getLogger(__name__)


class MteeUtils:
    def __init__(self, mtee_target=None, apinext_target=None):
        self.mtee_target = mtee_target
        self.apinext_target = apinext_target

    def move_artifacts_from_mtee_exc(self, list):
        pwd = os.getcwd()
        try:
            for x in list:
                shutil.move("{}/{}".format(pwd, x), "{}/results/".format(pwd))
        except Exception:
            raise

    def apply_adb_workaround(self):
        # https://asc.bmwgroup.net/mgujira/browse/HU22DM-3183

        logger.info("Applying usb peripheral hack for adb, only padi needs it.")
        result = self.mtee_target.execute_command("echo peripheral > /sys/devices/platform/soc/a600000.ssusb/mode")
        logger.info("ADB hack result: %s", result)
        result = self.mtee_target.execute_command("cat /sys/devices/platform/soc/a600000.ssusb/mode")
        logger.info("Content of /sys/devices/platform/soc/a600000.ssusb/mode: %s", result)

    def resume_default_conditions(self):
        if not lifecycle_tools.is_alive():
            lifecycle_tools.setup_keepalive()
            lifecycle_tools.wakeup_target()
            self.mtee_target.resume_after_reboot()

    def set_target_to_sleep(self, sleep_vehicle_condition=VehicleCondition.PARKEN_BN_NIO):
        """Set target to sleep state

        :param sleep_vehicle_condition: Which VehicleCondition should that target have when in sleep,
                                        defaults to VehicleCondition.PARKEN_BN_NIO
        :type sleep_vehicle_condition: VehicleCondition, optional
        """
        logger.info("Setting target to sleep")
        self.mtee_target.switch_vehicle_to_state(sleep_vehicle_condition)
        self.mtee_target.prepare_for_reboot()
        lifecycle_tools.stop_keepalive()
        if self.mtee_target.options.target == "rse22":
            lifecycle_tools.set_lifecycle_rear_entertainment_in_vcar(False)

        status_target = lifecycle_tools.is_alive()
        tries = 0
        while tries < 20 and status_target:
            tries += 1
            time.sleep(5)
            status_target = lifecycle_tools.is_alive()
            logger.debug("Target is alive? {}".format(status_target))

        assert lifecycle_tools.is_alive() is False, "Target didn't went to sleep mode"

    def wakeup_target(
        self,
        apply_adb_workaround=False,
        wait_for_adb_device=True,
        boot_vehicle_condition=VehicleCondition.FAHREN,
        boot_lc_rear_entertainment=True,
        boot_lc_rear_cyclic=True,
    ):
        """Perform a target wake up

        :param apply_adb_workaround: Set adb workaround, this is useful for padi, defaults to False
        :type apply_adb_workaround: bool, optional
        :param wait_for_adb_device: Wake up target and wait for adb device availability, defaults to True
        :type wait_for_adb_device: bool, optional
        :param boot_vehicle_condition: Which VehicleCondition should the target have after waking up,
                                     defaults to FAHREN
        :type boot_vehicle_condition: VehicleCondition, optional
        :param lc_rear_entertainment: Lifecycle rear entertainment value in vcar, defaults to True
        :type lc_rear_entertainment: bool, optional
        :param lc_rear_cyclic: Set lifecycle rear entertainment as a cyclic message, defaults to True
        :type lc_rear_cyclic: bool, optional
        """
        self.mtee_target.switch_vehicle_to_state(boot_vehicle_condition)
        time.sleep(2)
        if not lifecycle_tools.is_alive():
            logger.info("Waking up Target")
            lifecycle_tools.wakeup_target()
            lifecycle_tools.setup_keepalive()
            if self.mtee_target.options.target == "rse22":
                lifecycle_tools.set_lifecycle_rear_entertainment_in_vcar(
                    boot_lc_rear_entertainment, cyclic=boot_lc_rear_cyclic
                )
            self.mtee_target.resume_after_reboot()

        status_target = lifecycle_tools.is_alive()
        tries = 0
        while tries < 20 and not status_target:
            tries += 1
            time.sleep(5)
            status_target = lifecycle_tools.is_alive()
            logger.info("Target is alive? {}".format(status_target))

        assert lifecycle_tools.is_alive() is True, "Target didn't wake up"

        if apply_adb_workaround:
            self.apply_adb_workaround()

        if wait_for_adb_device:
            self.apinext_target.wait_for_adb_device(wait_time=120)

    def reboot_target(
        self,
        apply_adb_workaround=False,
        wait_for_adb_device=True,
        sleep_vehicle_condition=VehicleCondition.PARKEN_BN_NIO,
        boot_vehicle_condition=VehicleCondition.FAHREN,
        boot_lc_rear_entertainment=True,
        boot_lc_rear_cyclic=True,
    ):
        self.set_target_to_sleep(sleep_vehicle_condition=sleep_vehicle_condition)
        self.wakeup_target(
            apply_adb_workaround=apply_adb_workaround,
            wait_for_adb_device=wait_for_adb_device,
            boot_vehicle_condition=boot_vehicle_condition,
            boot_lc_rear_entertainment=boot_lc_rear_entertainment,
            boot_lc_rear_cyclic=boot_lc_rear_cyclic,
        )
        self.apinext_target.wait_for_boot_completed_flag()

    def restart_target_and_driver(self, test):
        """
        Reboot target and restart appium driver
        :param test: TestBase singleton object
        """
        if test.record_test:
            logger.info("Stopping current recording...")
            timestamp_now = str(datetime.strftime(datetime.now(), "%Y-%m-%d.%H-%M-%S.%f"))
            utils.stop_recording(test, timestamp_now)
        test.quit_driver()
        logger.info("Restarting the target...")
        self.mtee_target.reboot()
        self.apinext_target.wait_for_boot_completed_flag(wait_time=90)
        test.setup_driver()
        test.force_stop_package()
        utils.pop_up_check(test)
        if test.record_test:
            logger.info("Starting new recording after restart...")
            utils.start_recording(test)

    def change_language(self, language: Optional[str] = "en"):
        """
        :param language: Languages and Locales Supported by Android

        Find supported languages:
        http://www.apps4android.org/?p=3695
        https://asc.bmwgroup.net/wiki/display/APINEXT/Cerence+Country+Language+Matrix

        Expected
        Result:
        "result=0"
        """
        command = f"am broadcast -n com.bmwgroup.idnext.settings/.ChangeLocale --es language {language}"
        expected_output = "result=0"
        result = self.apinext_target.execute_command(command, privileged=True)
        assert expected_output in result, f"Unable to change language. Execution Failed with Output: {result}"

    def connect_to_internet(self, test):
        """
        Connect the target to internet
        """
        if not self.mtee_target.has_capability(TE.test_bench.rack):
            logger.info("Connect to internet ...")
            if self.apinext_target.check_internet_connectivity():
                logger.info("Target is already connected to internet. Skipping connection setup")
                return
            test.quit_driver()
            self.apinext_target.turn_off_airplane_mode()
            self.apinext_target.bootstrap_wifi()
            self.mtee_target.reboot()
            self.apinext_target.wait_for_boot_completed_flag(wait_time=90)
            self.apinext_target.enable_wifi_service()
            self.apinext_target.connect_to_wifi()
            if not self.apinext_target.check_internet_connectivity():
                raise RuntimeError("Internet connection was not successful")
            test.setup_driver()
            logger.info("Connect to internet ... done")
        else:
            logger.info("TRAAS setup should have backend connectivity and provisioning by default")

    def grant_permission(self, package, permission):
        """
        Grant permission for a particular package

        :param package - Android package
        :param permission - requested permission for package
        """
        user = self.apinext_target.get_current_user_id()
        command = f"pm grant --user {user} {package} {permission}"
        self.apinext_target.execute_command(command, privileged=True)

    def set_str_budget(self, str_budget="5616000"):
        """
        This function can be used to set the STR budget and validate whether budget got updated to expected value on
        DUT. Note : STR Budget is a new implementation in STR feature, and it needs to be up in order to successfully
        perform STR. By default, it can be set to 5616000 mAs
        """
        set_str_budget = ""
        set_str_budget_patt = re.compile(r".*Received remaining STR budget changing from (\d+) mAs to (\d+) mAs")
        with DLTContext(self.mtee_target.connectors.dlt.broker, filters=[("NSM", "NSMC")]) as traces:
            time.sleep(0.2)
            self.mtee_target.execute_command("inc-demo_io_lifecycle_SomeIp -j  " + str_budget)
            filter_dlt_messages = traces.wait_for(
                attrs={"apid": "NSM", "ctid": "NSMC", "payload_decoded": set_str_budget_patt},
                timeout=120,
                drop=True,
                count=0,
                raise_on_timeout=False,
            )
        # Collecting setstr budget value from traces.
        for msg in filter_dlt_messages:
            logger.info(f"Payload : {msg.payload_decoded}")
            matches = set_str_budget_patt.search(msg.payload_decoded)
            if matches:
                set_str_budget = matches.group(2)
                logger.info(f"STR budget updated to {set_str_budget} mAs")
                break
        assert_equal(
            str_budget, set_str_budget, f"Expected STR value: {str_budget}. Actual STR value: {set_str_budget}. "
        )

    def step_down_vehicle_state_to_parken(self):
        """
        Stepwise switching to PARKEN_BN_IO from PRUEFEN according to standard procedure
        """
        self.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.WOHNEN)
        logger.info("Vehicle in WOHNEN")
        self.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
        logger.info("Vehicle in STANDFUNCTION")
        self.mtee_target.prepare_for_reboot()
        self.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.PARKEN_BN_IO)
        logger.info("Switching to PARKEN")
