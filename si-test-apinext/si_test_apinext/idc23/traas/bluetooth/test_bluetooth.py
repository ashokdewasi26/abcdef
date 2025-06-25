import logging
import time

from mtee.testing.test_environment import require_environment, require_environment_setup
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_true, metadata
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.connector_bluetooth import ConnectorBluetoothIDC23
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack
VIDEO_NAME = "TestBluetooth"


@require_environment(*REQUIREMENTS)
@metadata(testsuite=["SI"])
class TestBluetooth:
    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        cls.bluetooth = ConnectorBluetoothIDC23(cls.test, cls.bluetooth_utils)
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)
        cls.bluetooth_utils.turn_on_bluetooth_via_adb_commands()
        cls.bluetooth.start()
        Connect.remove_all_paired_devices()

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        cls.bluetooth.stop()
        cls.bluetooth.delete_device_from_target()
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def setup(self):
        utils.start_recording(self.test)
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)

    def teardown(self):
        utils.stop_recording(self.test, VIDEO_NAME)
        time.sleep(1)

    @utils.gather_info_on_fail
    def test_001_pair_bluetooth(self):
        """
        Validate the bluetooth pairing functionality
        Precondition: turn on phonesimu in traas
        """
        assert_true(self.bluetooth.is_paired or self.bluetooth.pair_host_with_target())
        self.bluetooth_utils.ensure_bluetooth_services()

    @utils.gather_info_on_fail
    def test_002_bluetooth_reboot(self):
        """
        Check pairing resumed after reboot
        Like simulating an out of range device and then returning to range
        *Steps*
        1. Pair phonesimu Bluetooth with IDC
        2. Reboot IDC23
        3. Validate BT host pairing resumed
        """
        # Validate pairing / Validate BT host available
        assert_true(self.bluetooth.is_paired or self.bluetooth.pair_host_with_target())
        Connect.open_connectivity()
        self.bluetooth_utils.ensure_bluetooth_services()
        # Reboot IDC23
        self.mtee_utils.restart_target_and_driver(self.test)
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        Connect.open_connectivity()
        self.bluetooth_utils.ensure_bluetooth_services()
        assert_true(Connect.has_paired_device(), "No device paired")
