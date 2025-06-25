# Bluetooth service swither
from csv import writer
from itertools import cycle
import logging
import os
import socket
import telnetlib
import time

from mtee.testing.tools import TimeoutCondition
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.testing.connector_bluetooth import (
    CONN_AUDIO,
    CONN_AVRCP,
    CONN_HFP,
    PhoneSimuHandler,
    SUPPORTED_APPS,
)
import si_test_apinext.util.driver_utils as utils

PHONE_FREQUENCIES = [1500, 3000]
ENTERTAINMENT_FREQUENCIES = [4500, 6000]
SPEAKER_FREQUENCIES = [1000, 750]
PLAYING_STRENGTH = 0.5
NOT_PLAYING_STRENGTH = 1
ENTERTAINMENT_DURATION = 30.0
MAX_RESPONSE_TIME = 5.0
MAX_SWITCH_TIME = 40.0
DEFAULT_PHONE = 375
DEFAULT_ENTERTAINMENT = 1125
DEFAULT_SPEAKER = 2500

LIFECYCLES = 2

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


def connect_to_app(app, delay=1, retries=1):
    """Connects to the specified app and returns the sock on success"""
    if app in SUPPORTED_APPS:
        while retries:
            retries -= 1
            try:
                sock = telnetlib.Telnet()
                sock.open(*SUPPORTED_APPS[app])
                return sock
            except socket.error:
                sock.close()
                sock = None
                time.sleep(delay)
                logger.info(f"connecting to socket {SUPPORTED_APPS[app]}. retry = {retries}")
                continue
        raise RuntimeError(f"Could not connect to socket {SUPPORTED_APPS[app]}")
    raise TypeError("unsupported app")


class BluetoothEntertainment:
    """
    Bluetooth Media Service

    Phonesimu simulates audio signals, which is sent out from micro, and sends to IDC23:
                        phonesimu  --------> BT ---------->   IDC23
    Micro of phonesimu should also hear what is playing on IDC23:
                (HOST  <----- microphone) <--------- (speaker <------IDC23)
    """

    def __init__(self, test, phonesimu):
        self.test = test
        self.phonesimu = phonesimu
        self.ent_freq_to_play = cycle(ENTERTAINMENT_FREQUENCIES)
        self.entertainment_active = False
        self.entertainment_frequency_value = 0
        self.ent_latencies = []

    def init_entertainment(self):
        """The initial state of entertainment should be PLAYING, if bluetooth is selected as media source"""
        timer = TimeoutCondition(90)
        while timer:
            data = self.phonesimu.get_data()
            # Check if AVRCP is Up and Playing before starting test
            if data["avrcp"]["updated"]:
                if data["avrcp"]["status"] == "Playing":
                    self.set_next_playing_frequency()
                    break
                else:
                    self.set_next_playing_frequency()
                    time.sleep(2)
            else:
                logger.info("Waiting for phonesimu init")
                self.phonesimu.send_data(CONN_AVRCP, "status:\r\n".encode("utf-8"))
                time.sleep(1)
        else:
            raise TimeoutError("phonesimu failed to initialize. timeout = (90 seconds)")

    def terminate(self):
        self.phonesimu.send_data(CONN_AUDIO, "alsa-micro-recorder exit\r\n".encode("utf-8"))
        self.phonesimu.send_data(CONN_AUDIO, "sco-audio-recorder exit\r\n".encode("utf-8"))
        self.phonesimu.send_data(CONN_AUDIO, "alsa-micro exit\r\n".encode("utf-8"))
        # Resume Streaming State before rebooting or closing
        self.set_next_playing_frequency()

    def get_entertainment_status(self):
        data = self.phonesimu.get_data()
        entertainment_status = data["avrcp"]["status"]
        if entertainment_status == "Playing" and not self.entertainment_active:
            logger.info("Entertainment Started Playing")
            self.entertainment_active = True
            self.set_next_playing_frequency()
        elif entertainment_status == "Paused" or entertainment_status == "Stopped":
            logger.info(f"Entertainment {entertainment_status}")
            self.entertainment_active = False
            self.set_entertainment_frequency(0, 0)
        return entertainment_status

    def stop_audio(self, frequency=4500):
        """Stops the entertainment audio"""
        self.phonesimu.send_data(
            CONN_AUDIO,
            "a2dp-source set-signal-parameters {strength} {frequency}\r\n".format(
                strength=0, frequency=frequency
            ).encode("utf-8"),
        )
        # Ask phonesimu to synchronize A2DP state with MGU
        self.phonesimu.send_data(
            CONN_AUDIO,
            "a2dp-source set-signal-parameters {strength} {frequency}\r\n".format(strength=0, frequency=0).encode(
                "utf-8"
            ),
        )

    def set_entertainment_frequency(self, strength, frequency):
        """Generic API to set entertainment frequency"""
        self.entertainment_frequency_value = frequency
        self.phonesimu.send_data(
            CONN_AUDIO, "a2dp-source set-signal-parameters {} {}\r\n".format(strength, frequency).encode("utf-8")
        )

    def set_next_playing_frequency(self):
        """Set next entertainment frequency, which is determined by ent_freq_to_play"""
        self.set_entertainment_frequency(PLAYING_STRENGTH, next(self.ent_freq_to_play))

    @utils.gather_info_on_fail
    def validate_entertainment_from_ui(self, media_source_name):
        """Validate it is playing audio from bluetooth"""
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        if not Media.is_playing_source(media_source_name):
            screenshot = os.path.join(
                self.test.results_dir, f'No_playing_bt_media_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png'
            )
            self.test.apinext_target.take_screenshot(screenshot)
            raise AssertionError(f"Failed to select bluetooth as media source in {screenshot}")

    def is_simulating_entertainment_frequency(self):
        """Check if phonesimu is simulating the frequency of entertainment"""
        data = self.phonesimu.get_data()
        return data["micro"]["updated"] or (self.entertainment_frequency_value == data["entertainment"]["frequency"])

    def validate_entertainment_frequency(self):
        """
        Validate if what phonesimu hears from IDC23 is identical to what it sends to IDC23.

        :return: True, if phonesimu hears what it has sent; otherwise, False
        """
        data = self.phonesimu.get_data()
        if data["micro"]["frequency"] == data["entertainment"]["frequency"]:
            self.set_next_playing_frequency()
            ent_latency = data["micro"]["time"] - data["entertainment"]["time"]
            # Record the latency between sending and receiving
            logger.debug(f"Entertainment latency {ent_latency}")
            self.ent_latencies.append(ent_latency)
            return True
        return False

    def replay_entertainment(self):
        """Resume entertainment simulation"""
        self.phonesimu.send_data(CONN_AVRCP, "set-mode:paused\r\n".encode("utf-8"))
        time.sleep(2)
        self.phonesimu.send_data(CONN_AVRCP, "set-mode:playing\r\n".encode("utf-8"))
        time.sleep(2)

    def pause_entertainment(self):
        """Pause entertainment simulation"""
        self.phonesimu.send_data(CONN_AVRCP, "set-mode:stopped\r\n".encode("utf-8"))


class BluetoothTelephone:
    """
    Bluetooth Telephone Service consists of two parts: speaker and microphone

    SPEAKER of PHONESIMU: (what phonesimu hears from IDC23)
    Phonesimu simulates a person, who talks to phonesimu via IDC23:
            (phonesimu --> alsa-speaker)  -------------------> (microphone -----> IDC23)
    then, what this user talks is transfers via BT, and arrives phonesimu:
              phonesimu  <------------------ BT <----------------------- IDC23

    MICROPHONE of PHONESIMU: (what phonesimu talks to IDC23)
    Phonesimu simulates a talk frequency, which is sent to IDC23 via BT:
             phonesimu  ------------------> BT -----------------------> IDC23
    then, what IDC23 hears via BT could be heard from loudspeaker
        (host <--- microphone) <-------------------- (loudspeaker <----- IDC23)
    """

    def __init__(self, test, hfp_client_address, phonesimu):
        self.test = test
        self.phonesimu = phonesimu

        self.phone_frequency_value = 0
        self.speaker_frequency_value = 0
        self.phone_freq_to_play = cycle(PHONE_FREQUENCIES)
        self.speaker_freq_to_play = cycle(SPEAKER_FREQUENCIES)
        self.phone_latencies = []
        self.phone_active = False
        self.hfp_client_address = hfp_client_address

    def set_phone_frequency(self, strength, frequency):
        """Generic API to set phone frequency"""
        self.phone_frequency_value = frequency
        self.phonesimu.send_data(
            CONN_AUDIO, "sco-audio set-signal-parameters {} {}\r\n".format(strength, frequency).encode("utf-8")
        )

    def set_speaker_frequency(self, strength, frequency):
        """Generic API to set speaker frequency"""
        self.speaker_frequency_value = frequency
        self.phonesimu.send_data(
            CONN_AUDIO, "alsa-speaker set-signal-parameters {} {}\r\n".format(strength, frequency).encode("utf-8")
        )

    def simulate_outgoing_call(self):
        """Simulate outgoing calls"""
        self.phonesimu.send_data(CONN_HFP, "\r\nAT: ATD>1;\r\n".encode("utf-8"))
        self.phonesimu.send_data(
            CONN_AUDIO, "sco-audio connect {}\r\n".format(self.hfp_client_address).encode("utf-8")
        )

    def set_default_call_duration(self):
        """
        Set default 30 seconds as call duration, after 30s it terminates automatically.
        If you want to end the call by yourself, then do not call this method.
        """
        self.phonesimu.send_data(CONN_HFP, "DEFAULT: 30, 30, 5, 1, 30, 30\r\n".encode("utf-8"))

    def set_next_phone_frequency(self):
        """Set next phone frequency, which is determined by phone_freq_to_play"""
        self.set_phone_frequency(PLAYING_STRENGTH, next(self.phone_freq_to_play))

    def set_next_speaker_frequency(self):
        """Set next speaker frequency, which is determined by speaker_freq_to_play"""
        self.set_speaker_frequency(PLAYING_STRENGTH, next(self.speaker_freq_to_play))

    def validate_active_call_from_ui(self, occasion):
        """Validate the active call is displayed on IDC23"""
        if not Connect.is_active_call():
            screenshot = os.path.join(
                self.test.results_dir, f'No_call_display_{occasion}_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png'
            )
            self.test.apinext_target.take_screenshot(screenshot)
            # TODO: it should throw out AssertionError,
            #  but it fails because of delay in UI, Alexa pop-up, or other issues.
            # For the detected issues, please create tickets
            logger.error(f"After dialing, the call is not displayed in {screenshot}")

    @utils.gather_info_on_fail
    def phone_updated(self):
        """Update phone signals according to different states."""
        data = self.phonesimu.get_data()
        if data["phone"]["status"] == "1" and not self.phone_active:
            logger.info("Phone Call Beginning")
            self.phone_active = True
            self.set_next_phone_frequency()
            self.set_next_speaker_frequency()

            # Validate it is active call
            self.validate_active_call_from_ui("during_active_all")
        else:
            logger.info("Phone Call Ending")
            self.phone_active = False
            self.set_phone_frequency(NOT_PLAYING_STRENGTH, DEFAULT_PHONE)
            self.set_speaker_frequency(NOT_PLAYING_STRENGTH, DEFAULT_SPEAKER)

    def is_simulating_phone(self):
        """Check if it is simulating IDC23 microphone frequency"""
        data = self.phonesimu.get_data()
        return data["micro"]["updated"] or (self.phone_frequency_value == data["phone"]["frequency"])

    def validate_micro_frequency(self):
        """
        Expect
                "what phonesimu talks to IDC23"  == "what host hears from IDC23"

        :return: True, if the expectation matches; otherwise, False.
        """
        data = self.phonesimu.get_data()
        if data["micro"]["frequency"] == data["phone"]["frequency"]:
            phone_latency = self.data["micro"]["time"] - self.data["phone"]["time"]
            logger.debug(f"Phone latency {phone_latency} Incoming")
            self.phone_latencies.append(phone_latency)
            self.set_next_phone_frequency()
            return True
        return False

    def is_simulating_speaker(self):
        """Check if it is simulating IDC23 speaker frequency"""
        data = self.phonesimu.get_data()
        return data["sco"]["updated"] or (self.speaker_frequency_value == data["speaker"]["frequency"])

    def validate_speaker_frequency(self):
        """
        Expect
                "what user talks to IDC23"  == "what phonesimu hears via BT"

        :return: True, if the expectation matches; otherwise, False.
        """
        data = self.phonesimu.get_data()
        if data["sco"]["frequency"] == data["speaker"]["frequency"]:
            phone_latency = data["sco"]["time"] - data["speaker"]["time"]
            logger.debug(f"Phone latency {phone_latency} Outgoing")
            self.set_next_speaker_frequency()
            return True
        return False


class BluetoothServicesSwitcher:
    """Bluetooth Services Switcher"""

    def __init__(self, test):
        self.test = test

        self.speaker_frequency_req_time = 0
        self.entertainment_frequency_req_time = 0
        self.entertainment_active_time = 0
        self.last_activity_time = 0
        self.hfp_client_address = None
        self.avrcp_client_address = None
        self.total_entertainment_changes = 0
        self.total_phone_changes = 0
        self.total_speaker_changes = 0
        self.total_ent_pass = 0
        self.total_phone_out_pass = 0
        self.total_phone_in_pass = 0

        self.ent_report_name = os.path.join(os.getcwd())
        self.phone_report_name = os.path.join(os.getcwd())
        self.phone_frequency_req_time = time.time()
        self.stop_entertainment = False

        self.ent_failure_count = 0
        self.incoming_phone_failure_count = 0
        self.outgoing_phone_failure_count = 0
        self.switch_count = 0
        self.data = {}

        self.audio_sock = connect_to_app(CONN_AUDIO, delay=1, retries=5)
        self.avrcp_sock = connect_to_app(CONN_AVRCP, delay=1, retries=5)
        self.hfp_sock = connect_to_app(CONN_HFP, delay=1, retries=5)

        self.phonesimu = PhoneSimuHandler(
            [
                (CONN_AUDIO, self.audio_sock.get_socket()),
                (CONN_AVRCP, self.avrcp_sock.get_socket()),
                (CONN_HFP, self.hfp_sock.get_socket()),
            ],
            os.path.join(self.test.results_dir, "audio_telnet_" + time.strftime("%Y-%h-%d_%H-%M-%S") + ".log"),
        )

        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        self.phonesimu_entertainment = BluetoothEntertainment(self.test, self.phonesimu)
        self.phonesimu_telephone = BluetoothTelephone(self.test, self.hfp_client_address, self.phonesimu)

    def ensure_init_in_phonesimu(self):
        # Set correct starting conditions in phonesimu before starting iterations
        # Robust handling of phonesimu failures, make sure entertainment is playing
        self.phonesimu_entertainment.set_entertainment_frequency(
            NOT_PLAYING_STRENGTH, next(self.phonesimu_entertainment.ent_freq_to_play)
        )
        # Launch alsa micro worker
        logger.info("Launching new alsa-micro worker")
        self.phonesimu.send_data(
            CONN_AUDIO, "alsa-micro new-alsa-micro plughw:CARD=Device,DEV=0 48000\r\n".encode("utf-8")
        )
        # Record what phonesimu micro receives:
        #       alsa-micro  --> what it hears from IDC23 entertainment
        #       asco-audio  --> what it hears from IDC23 phone-speaker
        self.phonesimu.send_data(
            CONN_AUDIO,
            "alsa-micro record {} 0.1\r\n".format(os.path.join(self.test.results_dir, "ent_recording")).encode(
                "utf-8"
            ),
        )
        self.phonesimu.send_data(
            CONN_AUDIO,
            "sco-audio record {} 0.1\r\n".format(os.path.join(self.test.results_dir, "sco_recording")).encode("utf-8"),
        )
        # Entertainment should be "PLAYING" since bluetooth is selected as media source
        self.phonesimu_entertainment.init_entertainment()
        # Record the time
        self.entertainment_active_time = time.time()
        self.last_activity_time = self.entertainment_active_time

    def set_phone_frequency(self, strength, frequency):
        self.phonesimu_telephone.set_phone_frequency(strength, frequency)
        self.phone_frequency_req_time = time.time()

    def set_speaker_frequency(self, strength, frequency):
        self.phonesimu_telephone.set_speaker_frequency(strength, frequency)
        self.speaker_frequency_req_time = time.time()

    def set_entertainment_frequency(self, strength, frequency):
        self.phonesimu_entertainment.set_entertainment_frequency(strength, frequency)
        self.entertainment_frequency_req_time = time.time()

    def wait_for_dev_in_phonesimu(self):
        timer = TimeoutCondition(90)
        while timer:
            logger.info("Waiting for HFP & AVRCP device")
            data = self.phonesimu.get_data(refresh=False)
            if data["hfp_cli_addr"]:
                self.hfp_client_address = data["hfp_cli_addr"]

            if data["avrcp"]["addr"]:
                self.avrcp_client_address = data["avrcp"]["addr"]

            if self.avrcp_client_address and self.hfp_client_address:
                break

            self.phonesimu.send_data(CONN_HFP, "HF-STATUS:\r\n".encode("utf-8"))
            self.phonesimu.send_data(CONN_AVRCP, "ct-status:\r\n".encode("utf-8"))
            time.sleep(0.5)
        else:
            raise TimeoutError("Device Discovery failed. timeout = (90 seconds)")

        logger.info(f"HFP device is {self.hfp_client_address}")

    def ensure_teardown_phonesimu(self):
        if self.phonesimu._started:
            self.phonesimu_entertainment.terminate()
            time.sleep(1)
            self.phonesimu.stop_comm()

    def entertainment_updated(self):
        self.last_activity_time = time.time()
        if self.phonesimu_entertainment.get_entertainment_status() == "Playing":
            self.total_entertainment_changes += 1
            self.entertainment_active_time = self.entertainment_frequency_req_time

    @utils.gather_info_on_fail
    def phone_updated(self):
        self.last_activity_time = time.time()
        self.phonesimu_telephone.phone_updated()
        if self.phonesimu_telephone.phone_active:
            self.total_phone_changes += 1
            self.total_speaker_changes += 1
        else:
            self.switch_count += 1
            self.phonesimu_entertainment.replay_entertainment()
            logger.info(f"Successfully made Switch Number: {self.switch_count}")

    def act_on_entertainment(self, current_time, media_source_name):
        # Entertainment is interrupted by the phone call
        if current_time - self.entertainment_active_time >= ENTERTAINMENT_DURATION:
            self.phonesimu_entertainment.pause_entertainment()

            logger.info("Entertainment Audio Time Up. Starting Phone Call.")
            self.phonesimu_telephone.simulate_outgoing_call()
            self.stop_entertainment = True

            time.sleep(2)
            self.phonesimu_telephone.validate_active_call_from_ui("after_dialing")

            return True

        # Validate it is playing audio from bluetooth
        self.phonesimu_entertainment.validate_entertainment_from_ui(media_source_name)
        # Micro can sometimes report back earlier than playback reports the played back frequency.
        # In this case we need to also check when the frequency played back matches what
        # we played. If it matches what we played then we check if the last micro update
        # also recorded the same played frequency. This way we make a stronger check i.e.
        # wanted to play == played == recorded
        if self.phonesimu_entertainment.is_simulating_entertainment_frequency():
            if self.phonesimu_entertainment.validate_entertainment_frequency():
                self.total_ent_pass += 1
                self.total_entertainment_changes += 1
            elif current_time - self.entertainment_frequency_req_time > MAX_RESPONSE_TIME:
                logger.error(
                    f"Failure: Entertainment audio not responding, "
                    f'Entertainment Freq Reported: {self.data["entertainment"]["frequency"]}Hz '
                    f"Entertainment Freq Set: {self.phonesimu_entertainment.entertainment_frequency_value}Hz "
                    f'Entertainment Freq Recorded: {self.data["micro"]["frequency"]}Hz'
                )

                self.ent_failure_count += 1
                self.total_entertainment_changes += 1
                self.phonesimu_entertainment.set_next_playing_frequency()

        return False

    def act_on_phone(self, current_time):
        self.stop_entertainment = False
        # Phone is automatically stopped after a delay
        # Micro can sometimes report back earlier than playback reports the played back frequency.
        # In this case we need to also check when the frequency played back matches what
        # we played. If it matches what we played then we check if the last micro update
        # also recorded the same played frequency. This way we make a stronger check i.e.
        # wanted to play == played == recorded
        if self.phonesimu_telephone.is_simulating_phone():
            if self.phonesimu_telephone.validate_micro_frequency():
                self.total_phone_in_pass += 1
                self.total_phone_changes += 1
            elif current_time - self.phone_frequency_req_time > MAX_RESPONSE_TIME:
                logger.error("Failure: Incoming Phone audio not responding")
                logger.debug(
                    f"Incoming Frequency Set: {self.phonesimu_telephone.phone_frequency_value}Hz "
                    f'Frequency Played: {self.data["phone"]["frequency"]}Hz '
                    f'Frequency Recorded: {self.data["micro"]["frequency"]}hz'
                )
                self.incoming_phone_failure_count += 1
                self.total_phone_changes += 1
                self.phonesimu_telephone.set_next_phone_frequency()

        if self.phonesimu_telephone.is_simulating_speaker():
            if self.phonesimu_telephone.validate_speaker_frequency():
                self.total_phone_out_pass += 1
                self.total_speaker_changes += 1
            elif current_time - self.speaker_frequency_req_time > MAX_RESPONSE_TIME:
                logger.error("Failure: Outgoing Phone audio not responding")
                logger.debug(
                    f"Outgoing Frequency Set: {self.phonesimu_telephone.speaker_frequency_value}Hz "
                    f'Frequency Played: {self.data["speaker"]["frequency"]}Hz '
                    f'Frequency Recorded: {self.data["sco"]["frequency"]}hz'
                )
                self.phonesimu_telephone.set_next_speaker_frequency()
                self.outgoing_phone_failure_count += 1
                self.total_speaker_changes += 1

    def assess_and_report(self):  # pylint: disable=too-many-branches,too-many-statements
        ent_latency = {}
        phone_latency = {}
        logger.info(f"Number of Switches: {self.switch_count}")
        if self.total_entertainment_changes:
            logger.info(
                f"Entertainment Failure "
                f"rate {float(self.ent_failure_count) / float(self.total_entertainment_changes) * 100}%% "
                f"({self.total_ent_pass}/{self.ent_failure_count}/{self.total_entertainment_changes})"
            )
        if self.total_phone_changes:
            logger.info(
                f"Incoming Phone Failure "
                f"rate {float(self.incoming_phone_failure_count) / float(self.total_phone_changes) * 100}%% "
                f'({self.total_phone_in_pass}/{self.incoming_phone_failure_count}/{self.total_phone_changes})"'
            )
        if self.total_speaker_changes:
            logger.info(
                f"Outgoing Phone Failure "
                f"rate {float(self.outgoing_phone_failure_count) / float(self.total_speaker_changes) * 100}%% "
                f"({self.total_phone_out_pass}/{self.outgoing_phone_failure_count}/{self.total_speaker_changes})"
            )
        phone_latencies = [round(lat, 4) for lat in self.phonesimu_telephone.phone_latencies if lat > 0.0]
        if not phone_latencies:
            logger.error("Less than once phone call test ran.. so phone latencies can't be calculated")
        else:
            phone_latency["max"] = max(phone_latencies)
            phone_latency["min"] = min(phone_latencies)
            phone_latency["avg"] = round(sum(phone_latencies) / len(phone_latencies), 4)
            phone_latency["med"] = sorted(phone_latencies)[int(len(phone_latencies) / 2)]
            logger.info(
                f'Phone Latencies. Max={phone_latency["max"]} Min={phone_latency["min"]} '
                f'Avg={phone_latency["avg"]} Median={phone_latency["med"]}'
            )
        ent_latencies = [round(lat, 4) for lat in self.phonesimu_entertainment.ent_latencies if lat > 0.0]
        if not ent_latencies:
            logger.info("Less than once ent test ran.. so entertainment latencies can't be calculated")
        else:
            ent_latency["max"] = max(ent_latencies)
            ent_latency["min"] = min(ent_latencies)
            ent_latency["avg"] = round(sum(ent_latencies) / len(ent_latencies), 4)
            ent_latency["med"] = sorted(ent_latencies)[int(len(ent_latencies) / 2)]
            logger.info(
                f'Entertainment Latencies. Max={ent_latency["max"]} Min={ent_latency["min"]} '
                f'Avg={ent_latency["avg"]} Median={ent_latency["med"]}'
            )
        if not phone_latencies:
            raise AssertionError(
                "Bluetooth Endurance Test Failed."
                " Less than once phone call test ran.. so phone latencies can't be calculated"
            )

        if not ent_latencies:
            raise AssertionError(
                "Bluetooth Endurance Test Failed."
                " Less than once ent test ran.. so entertainment latencies can't be calculated"
            )

    def prepare_reports(self):
        reports_dir = os.path.join(self.test.results_dir, "endurance_report")
        if not os.path.exists(reports_dir):
            logger.info(f"Creating recordings directory '{reports_dir}'")
            os.makedirs(reports_dir)

        self.ent_report_name = os.path.join(reports_dir, "bt_ent.csv")
        self.phone_report_name = os.path.join(reports_dir, "bt_phone.csv")

        with open(self.ent_report_name, "w+") as report_file:
            report = writer(report_file)
            report.writerow(
                [
                    "Lifecycle",
                    "switches",
                    "ent_failure_rate",
                    "ent_failures",
                    "ent_total",
                    "latency_max",
                    "latency_min",
                    "latency_avg",
                    "latency_median",
                    "color",
                ]
            )

        with open(self.phone_report_name, "w+") as report_file:
            report = writer(report_file)
            report.writerow(
                [
                    "Lifecycle",
                    "switches",
                    "outgoing_failure_rate",
                    "outgoing_failures",
                    "outgoing_total",
                    "incoming_failure_rate",
                    "incoming_failures",
                    "incoming_total",
                    "latency_max",
                    "latency_min",
                    "latency_avg",
                    "latency_median",
                    "color",
                ]
            )

    @utils.gather_info_on_fail
    def switch_bluetooth_services(self, media_source_name, switch_count, assert_and_report=False):
        self.phonesimu_entertainment.entertainment_active = True
        self.phonesimu_entertainment.ent_latencies = []
        self.phonesimu_telephone.phone_latencies = []
        self.stop_entertainment = False
        self.phonesimu_telephone.phone_active = False
        self.ent_failure_count = 0
        self.incoming_phone_failure_count = 0
        self.outgoing_phone_failure_count = 0
        self.switch_count = 0
        self.data = {}

        self.phonesimu.start_comm()
        self.phonesimu_entertainment.stop_audio()
        self.set_phone_frequency(NOT_PLAYING_STRENGTH, DEFAULT_PHONE)
        self.phonesimu_telephone.set_default_call_duration()
        self.wait_for_dev_in_phonesimu()
        # Entertainment is active after this step
        self.ensure_init_in_phonesimu()

        try:
            while self.switch_count < switch_count:
                self.data = self.phonesimu.get_data()
                if self.data["avrcp"]["updated"]:
                    self.entertainment_updated()

                if self.data["phone"]["updated"]:
                    self.phone_updated()

                current_time = time.time()
                if current_time - self.last_activity_time > MAX_SWITCH_TIME:
                    logger.error(
                        f"Switching Failed: Phone Status:{str(self.phonesimu_telephone.phone_active)} "
                        f"Entertainment Status:{str(self.phonesimu_entertainment.entertainment_active)}"
                    )
                    raise AssertionError(
                        f"Bluetooth Endurance Test Failed Phone: {str(self.phonesimu_telephone.phone_active)}, "
                        f"Entertainment: {str(self.phonesimu_entertainment.entertainment_active)})"
                    )

                if self.phonesimu_telephone.phone_active and self.phonesimu_entertainment.entertainment_active:
                    logger.info("Phone and Entertainment are both active")
                    continue

                if self.phonesimu_entertainment.entertainment_active and not self.stop_entertainment:
                    if self.act_on_entertainment(current_time, media_source_name):
                        continue

                if self.phonesimu_telephone.phone_active:
                    self.act_on_phone(current_time)
        finally:
            if assert_and_report:
                self.assess_and_report()
