import logging
import os
import re
import time

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import TimeoutError as MteeTimeoutError
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.mtee_utils import MteeUtils
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions

logger = logging.getLogger(__name__)


class TestShutdown:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.lc = LifecycleFunctions()
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()

    def _trigger_sleep(self):
        """Trigger ecu into sleep"""
        self.test.mtee_target.prepare_for_reboot()
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_NIO)
        self.lc.stop_keepalive()

    def _trigger_wakeup(self):
        """Trigger wakeup of the ECU by setting FAHREN state"""
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        self.test.mtee_target.wakeup_from_sleep()
        self.lc.setup_keepalive()
        self.test.mtee_target.resume_after_reboot()

    @utils.gather_info_on_fail
    def test_cancel_shutdown(self):
        """
        Test cancel shutdown

        *Background information*

        This test case checks the functionality of cancel shutdown sequence:
        * ECU goes to sleep (normal shutdown)
        * Shutdown is cancelled before it is completed, therefore ECU wakes up again from sleep

        *Steps*
        1. Send normal shutdown event
        2. Validate normal shutdown procedure
        3. Send runup event before shutdown has been completed
        4. Validate runup event procedure
        5. Validate that IDC is functional and all applications are usable
        6. Reboot target and check target is usable
        """
        self.test.teardown_base_class()
        with DLTContext(
            self.test.mtee_target.connectors.dlt.broker, filters=[("NSM", "NSM"), ("NSM", "NSMA")]
        ) as trace:
            for sleep_time in range(1, 20):
                try:
                    self._trigger_sleep()
                    msg = "NSM: Informed"  # NSM log after informing clients, e.g. NSM: Informed 24 clients!...
                    trace.wait_for(
                        attrs=dict(payload_decoded=re.compile(f".*{msg}.*"), apid="NSM", ctid="NSM"),
                        drop=True,
                    )

                    # Waiting before triggering wakeup to make sure the shutdown sequence initializes
                    logger.debug("Sleeping {}s then waking up".format(sleep_time))
                    time.sleep(sleep_time)
                    self._trigger_wakeup()

                    msg = "NSM_SHUTDOWNTYPE_RUNUP"
                    trace.wait_for(
                        attrs=dict(payload_decoded=re.compile(f".*{msg}.*"), apid="NSM", ctid="NSMA"),
                        drop=True,
                    )

                    msg = "Changed NodeState.*Resume.*NsmNodeState_FullyOperational"
                    trace.wait_for(
                        attrs=dict(payload_decoded=re.compile(f".*{msg}.*"), apid="NSM", ctid="NSM"),
                        skip=True,
                    )
                    break
                except MteeTimeoutError:
                    pass
            else:
                raise AssertionError("Unable to set cancel shutdown.")

        self.test.setup_apinext_target()
        after_cancel_shutdown_screenshot = os.path.join(self.test.results_dir, "CID_after_cancel_shutdown.png")
        self.test.apinext_target.take_screenshot(after_cancel_shutdown_screenshot)

        self.test.setup_base_class()
        Launcher.validate_launcher()
        Launcher.go_to_home()

        # Do an extra operation on android, in this case open media page
        Media.open_media()
        Launcher.go_to_home()

        # Check if is able to reboot target - see HU22DM-31888
        self.mtee_utils.restart_target_and_driver(self.test)

        # Check again media activity
        Media.open_media()
        Launcher.go_to_home()
