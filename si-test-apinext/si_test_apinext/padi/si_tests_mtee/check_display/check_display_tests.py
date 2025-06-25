import logging
import os
import re
import time

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import TimeoutError as MteeTimeoutError
from si_test_apinext.padi import DISPLAY_REF_IMAGES_PATH
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.mtee_utils import MteeUtils
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions

logger = logging.getLogger(__name__)
lifecycle_tools = LifecycleFunctions()


class TestCheckDisplay:
    display_ref_images_path = DISPLAY_REF_IMAGES_PATH
    mtee_log_plugin = True

    _screenshot_list = []

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_apinext_target()
        cls.vcar_manager = TargetShare().vcar_manager
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        # This set is required to enable PADI get FZD commands.
        # FZD CAN version (low) => FZD send commands to BCP (vcar), then its forward from BCP to PADI (160.48.199.16)
        # FZD SOME/IP version (high) => FZD send commands directly to PADI (160.48.199.86)
        cls.test.mtee_target.execute_command("devcoding write FZD_VARIANT 1")
        # Place correct default values for kinematics work
        # cls.__test_vcar_values(cls)
        cls.default_statusPosition = cls.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition")
        cls.mtee_utils.reboot_target(apply_adb_workaround=True)
        cls.test.setup_apinext_target()

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()
        cls.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition = {cls.default_statusPosition}")
        cls.mtee_utils.reboot_target(apply_adb_workaround=True)

    def __periodic_checks(self, dlt_detector):
        error_msgs = ""
        try:
            msg_ioaa = "touchPressed:"
            msg_nsmc = "touch pressed"
            msg_lcmg = "RSE received touch"
            res_msgs = dlt_detector.wait_for_multi_filters(
                filters=[
                    {"apid": "IOA", "ctid": "IOAA", "payload_decoded": re.compile(rf".*{msg_ioaa}.*")},
                    {"apid": "NSM", "ctid": "NSMC", "payload_decoded": re.compile(rf".*{msg_nsmc}.*")},
                    {"apid": "NSM", "ctid": "LCMG", "payload_decoded": re.compile(rf".*{msg_lcmg}.*")},
                ],
                drop=True,
                count=0,
                timeout=50,
            )
            msgs = []
            for msg in res_msgs:
                if (msg.apid == "IOA" and msg.ctid == "IOAA" and "true" in msg.payload_decoded) or msg.apid in (
                    "NSM",
                    "ALD",
                ):
                    msgs.append(msg.payload_decoded)

            logger.error("Found issue when checking dlts. Got %s", msgs)
            error_msgs = " ; ".join(msgs)
        except MteeTimeoutError:
            pass
        return error_msgs

    def test_001_check_display_on_boot(self):
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition = 2")
        time.sleep(2)

        error_msgs = {}

        for lc in range(250):
            with DLTContext(
                self.test.mtee_target.connectors.dlt.broker,
                filters=[("NSM", "LCMG"), ("NSM", "NSMC"), ("IOA", "IOAA")],
            ) as dlt_detector:
                screenshot_dir = os.path.join(self.test.results_dir, f"check_display_lc_screenshots/{lc}")
                os.makedirs(screenshot_dir, exist_ok=True)
                lc_key = "Issues on reboot num: " + str(lc)
                error_msgs[lc_key] = None

                logger.info("Trying with parken-wohnen")

                self.mtee_utils.set_target_to_sleep()

                self.mtee_utils.wakeup_target(
                    apply_adb_workaround=True,
                    boot_vehicle_condition=VehicleCondition.WOHNEN,
                    boot_lc_rear_entertainment=False,
                    boot_lc_rear_cyclic=False,
                )

                # logger.info("Taking screenshot before checks reboot")
                # self.test.apinext_target.take_screenshot(
                #     os.path.join(screenshot_dir, "launcher_check_display_pre.png")
                # )

                error_msgs[lc_key] = self.__periodic_checks(dlt_detector)

                # self.test.apinext_target.take_screenshot(
                #     os.path.join(screenshot_dir, "launcher_check_display_post.png")
                # )
                # comp_images_msgs = []
                # for img_name in os.listdir(screenshot_dir):
                #     img = os.path.join(screenshot_dir, img_name)
                #     res = compare_images(img, os.path.join(self.display_ref_images_path, "display_off.png"))
                #     if not res:
                #         comp_images_msgs.append(f"Image {img} is not black/empty")

                if error_msgs[lc_key]:
                    error_msgs[lc_key] = error_msgs[lc_key] + " ; "

                # error_msgs[lc_key] = error_msgs[lc_key] + " ; ".join(comp_images_msgs)

        error_msg = "\n".join([f"{lc}:{msg_list}" for lc, msg_list in error_msgs.items() if msg_list])

        assert not error_msg, error_msg
