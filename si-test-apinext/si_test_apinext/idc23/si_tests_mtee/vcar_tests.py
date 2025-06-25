import logging
import time

from mtee.testing.support.target_share import TargetShare
from si_test_apinext.testing.test_base import TestBase
from tee.target_common import VehicleCondition

logger = logging.getLogger(__name__)
AudioVolume = "SteeringWheelPushButton.statusAudioVolumeButton.operationPushButtonAudioAudioVolumeSteeringWheel"


class TestVcar:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.teardown_base_class()

    def test_vcar(self):

        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        # Exectute an adb shell command
        echo_command = self.test.apinext_target.execute_command(["echo", "1"])
        assert echo_command.stdout.startswith(b"1"), "The shell echo command should output 1"

        vcar_manager = TargetShare().vcar_manager
        if vcar_manager:
            logger.debug("Sending Press MFL Button")
            vcar_manager.send("{}= 1".format(AudioVolume))
            time.sleep(1)
            vcar_manager.send("{}= 0".format(AudioVolume))
        else:
            logger.error("vcar manager not available")
            raise RuntimeError("vcar is not available")
