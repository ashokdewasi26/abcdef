import time

from mtee.testing.test_environment import require_environment, require_environment_setup
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import metadata
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.bluetooth_service_switcher import BluetoothServicesSwitcher
from si_test_apinext.testing.connector_bluetooth import ConnectorBluetoothIDC23
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.mtee_utils import MteeUtils

REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack


@require_environment(*REQUIREMENTS)
@metadata(testsuite=["SI"])
class TestBluetoothEndurance:
    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.bluetooth_services_switcher = BluetoothServicesSwitcher(cls.test)
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        cls.bluetooth = ConnectorBluetoothIDC23(cls.test, cls.bluetooth_utils)
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)
        cls.bluetooth_utils.turn_on_bluetooth_via_adb_commands()
        cls.bluetooth.start()
        Connect.remove_all_paired_devices()
        utils.start_recording(cls.test)

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        video_name = "TestBluetoothEndurance"
        utils.stop_recording(cls.test, video_name)
        # If some test case is skipped, then phonesimu is not active and no need to kill services
        cls.bluetooth_services_switcher.ensure_teardown_phonesimu()
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_001_telephony_media_switches(self):
        # If there are already connected devices, then we should firstly remove all connected devices
        self.bluetooth.pair_host_with_target()
        try:
            # Ensure both phone & media services are supported by bluetooth
            Connect.open_connectivity()
            self.bluetooth_utils.ensure_bluetooth_services()

            self.bluetooth.enter_bt_audio_menu()
            time.sleep(1)
            self.bluetooth_services_switcher.switch_bluetooth_services(self.bluetooth.media_source_name, 2)
        finally:
            self.bluetooth.stop()
            self.bluetooth.delete_device_from_target()
