# Copyright (C) 2022. BMW CTW. All rights reserved.
import logging
import time

logger = logging.getLogger(__name__)

MAX_VOLUME_STEPS = 57


class VolumeController(object):
    """Volume controller"""

    def __init__(self, vcar):
        """
        Volume controller

        :param instance vcar: instance of a vcar object
        """
        self.vcar_manager = vcar

    def _send_volume_control_message(self, rotation_direction, steps):
        """Regulate volume with center stack scroller up or down"""

        self.vcar_manager.send("CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerDirectionOfRotation=0")
        self.vcar_manager.send("CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerIncrements=0")
        time.sleep(0.2)
        output = ""
        output += self.vcar_manager.send(
            "CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerDirectionOfRotation={}".format(
                rotation_direction
            )
        )
        output += self.vcar_manager.send(
            "CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerIncrements={}".format(abs(steps))
        )
        time.sleep(0.2)
        self.vcar_manager.send("CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerDirectionOfRotation=0")
        self.vcar_manager.send("CenterStack.statusAudioVolumeButtonCS.statusRotaryControllerIncrements=0")
        return output

    def increase_volume(self, steps=1):
        """Increase volume by given steps through center stack scroller"""
        self._send_volume_control_message(rotation_direction=2, steps=steps)

    def decrease_volume(self, steps=1):
        """Decrease volume by given steps through center stack scroller"""
        self._send_volume_control_message(rotation_direction=1, steps=steps)

    def mute_volume(self):
        """Mute volume"""
        self.decrease_volume(MAX_VOLUME_STEPS)

    def max_volume(self):
        """Max volume"""
        self.increase_volume(MAX_VOLUME_STEPS)

    def half_volume(self):
        """Volume to 50%"""
        self.increase_volume(round(MAX_VOLUME_STEPS / 2))

    def initialize_volume(self):
        """Initialize volume level"""
        self.mute_volume()  # Mute
        time.sleep(1.0)
        self.half_volume()  # Set initial level 50%
