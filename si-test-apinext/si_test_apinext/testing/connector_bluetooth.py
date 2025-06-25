# Bluetooth helper
import copy
import logging
import os
import queue
import re
import select
import subprocess
import threading
import time

from gen22_helpers.connectors.connector_bluetooth import ConnectorBluetooth
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import retry_on_except, TimeoutCondition
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media

POLL_TIMEOUT = 100
END_OF_LINE = b"\x0d\x0a"
CONN_AUDIO = "audio"
CONN_AVRCP = "avrcp"
CONN_HFP = "hfp"

INST_FREQ_MEASURE = 513

# 0.01 is a strength barrier which differentiates noise and proper signal.
MIN_DETECTION_STRENGTH = 0.01
LONG_FREQ_MEASURE = 2000

SUPPORTED_APPS = {
    CONN_AUDIO: ("127.0.0.1", 3000),  # A2DP, SCO
    CONN_AVRCP: ("127.0.0.1", 3001),  # Audio/Video remote control protocol
    CONN_HFP: ("127.0.0.1", 3002),  # Hands-free protocol --> telephony
}

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

dlt_filters = [("ALD", "LCAT")]
dlt_filter_dict = {"apid": "ALD", "ctid": "LCAT"}


def find_matched_dlt(dlt_messages, regex):
    """Find payload of the matched dlt from batch"""
    for dlt_msg in dlt_messages:
        payload = dlt_msg.payload_decoded
        if re.search(regex, payload):
            return payload


class ConnectorBluetoothIDC23(ConnectorBluetooth):
    """Implementation of bluetooh for IDC23"""

    def __init__(self, test, bluetooth_utils):
        super().__init__(test.mtee_target)
        self.apinext_target = test.apinext_target
        self.results_dir = test.results_dir
        self.bluetooth_utils = bluetooth_utils

    @property
    def media_source_name(self):
        """After start() is called, then self.host_bt_address is known"""
        return "SITESTS-" + self.host_bt_address

    def get_target_bt_address(self):
        """
        Returns IDC23 BT address
        """
        # Activate bluetooth from target, so that we could get its mac address
        self.bluetooth_utils.turn_on_bluetooth()
        Connect.open_connectivity()
        self.apinext_target.take_screenshot(os.path.join(self.results_dir, "try_to_discover_host_bt.png"))
        bluetooth_status_str = self.apinext_target.execute_adb_command(
            ["shell", "dumpsys", "bluetooth_manager"]
        ).strip()
        # Find the mac address from above string
        mac_regex = re.compile(r"(?:[0-9a-fA-F]:?){12}")
        mac_list = re.findall(mac_regex, bluetooth_status_str)
        if not mac_list:
            raise RuntimeError(f"Failed to find mac address from {bluetooth_status_str}")
        return mac_list[0]

    def discover_host_bt_from_target(self):
        """Stage1: idc23 discovers host bt"""
        with DLTContext(self._target.connectors.dlt.broker, filters=dlt_filters) as dlt_detector:
            self.bluetooth_utils.turn_on_bluetooth()
            Connect.open_connectivity()
            self.apinext_target.take_screenshot(
                os.path.join(self.results_dir, f"try_to_discover_host_{self.host_bt_address}.png")
            )
            bt_found = re.compile(
                rf"ConnectivityApp.*NewDeviceWizardViewModel\[.*\] ::updateNearbyAndPairedDevices, new set "
                rf"\[.*SITests-{self.host_bt_address}:{self.host_bt_address}.*\]"
            )
            host_discover_wait_time = 120

            timeout = TimeoutCondition(host_discover_wait_time)
            while timeout:
                dlt_messages = dlt_detector.wait_for(
                    dlt_filter_dict, timeout=60, skip=True, count=50, raise_on_timeout=False
                )
                matched_payload = find_matched_dlt(dlt_messages, bt_found)
                if matched_payload:
                    logger.debug("Bluebooth pairing stage 1: " + str(matched_payload))
                    return
            else:
                raise TimeoutError("Failed to detect host " + self.host_bt_address)

    @retry_on_except(exception_class=RuntimeError, retry_count=2, backoff_time=2, silent_fail=False)
    def pair_bt_after_discovery(self):
        """Pair host with target. In case of exception, retry three times"""
        try:
            self.send_pairing_request_from_host()
            self.confirm_pairing_from_target()
        except TimeoutError:
            self.bluetooth_utils.turn_on_bluetooth()
            Connect.open_connectivity()
            # If not paired, then retry again
            if not Connect.has_paired_device():
                self.apinext_target.take_screenshot(
                    os.path.join(self.results_dir, f'retry_pairing_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
                )
                raise RuntimeError("Failed to pair bt")

    def send_pairing_request_from_host(self):
        """Stage2: phonesimu sends pairing request to IDC23"""
        with DLTContext(self._target.connectors.dlt.broker, filters=dlt_filters) as dlt_detector:
            self._target.log_to_dlt("Phonesim: start to send pairing request...")
            self._bluez_controller.write(b"pair: %s\r\n" % self.target_bt_address.encode("ascii"))
            self._bluez_controller.read_until(b"RequestConfirmation", timeout=120)
            self._target.log_to_dlt("Phonesim: request is confirmed by bluez")

            bt_pair_discovery = re.compile(
                rf"ConnectivityApp.*PairingRequestReceived.*SITests-{self.host_bt_address}"
                rf":{self.host_bt_address}.*"
            )

            timeout = TimeoutCondition(120)
            while timeout:
                dlt_messages = dlt_detector.wait_for(
                    dlt_filter_dict, timeout=120, skip=True, count=50, raise_on_timeout=False
                )
                matched_payload = find_matched_dlt(dlt_messages, bt_pair_discovery)
                if matched_payload:
                    self.apinext_target.take_screenshot(
                        os.path.join(self.results_dir, f'confirmation_popup_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
                    )
                    logger.debug("Bluebooth pairing stage 2: " + str(matched_payload))
                    return
            else:
                raise TimeoutError("Failed to get pairing request from host " + self.host_bt_address)

    def confirm_pairing_from_target(self):
        """Stage3: confirm the pairing from IDC23"""
        # Sometimes, IDC23 has persistency for this device, and it might not need confirmation from IDC23 side
        if Connect.has_paired_device():
            self.apinext_target.take_screenshot(
                os.path.join(self.results_dir, f'pair_done_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
            )
            return

        # Normal case: a confirmation from IDC23 is required
        with DLTContext(self._target.connectors.dlt.broker, filters=dlt_filters) as dlt_detector:
            # IDC23 confirms the pairing
            Connect.confirm_pairing()
            self._target.log_to_dlt("IDC23: confirm pairing")
            self.apinext_target.take_screenshot(
                os.path.join(self.results_dir, f'confirmed_pairing_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
            )

            # Wait until the confirmation dlt is received
            pairing_done = re.compile(r"ConnectivityApp.*BluetoothDevicesRepository.*isBluetoothEnabled:.*")
            timeout = TimeoutCondition(120)
            while timeout:
                dlt_messages = dlt_detector.wait_for(
                    dlt_filter_dict, timeout=120, skip=True, count=50, raise_on_timeout=False
                )
                matched_payload = find_matched_dlt(dlt_messages, pairing_done)
                if matched_payload:
                    logger.debug("Bluebooth pairing stage 3: " + str(matched_payload))
                    break
            else:
                raise TimeoutError("Failed to confirm pairing from IDC23")

            pairing_png = None
            for retry in range(0, 3):
                time.sleep(5)
                Connect.open_connectivity()
                pairing_png = os.path.join(
                    self.results_dir, f'pairing_done_{retry}_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png'
                )
                self.apinext_target.take_screenshot(pairing_png)
                # Validate if "Bluetooth telephony" is displayed
                if Connect.has_paired_device():
                    break
            else:
                raise TimeoutError(f'Failed to find "Bluetooth telephony" in {pairing_png}')

    def delete_device_from_target(self):
        """Enter into first paired device menu in IDC23, and delete it"""
        with DLTContext(self._target.connectors.dlt.broker, filters=dlt_filters) as dlt_detector:
            Connect.open_connectivity()
            Connect.remove_pairing()

            self._target.log_to_dlt("IDC23: remove host device")
            logger.info("Disconnecting the host device from IDC23")

            # Wait until the confirmation dlt is received
            remove_done = re.compile(
                r"BluetoothDevice.*removeBond\(\) for device {host_address}"
                r" .*".format(host_address=self.host_bt_address)
            )
            timeout = TimeoutCondition(120)
            while timeout:
                dlt_messages = dlt_detector.wait_for(
                    dlt_filter_dict, timeout=120, skip=True, count=50, raise_on_timeout=False
                )
                matched_payload = find_matched_dlt(dlt_messages, remove_done)
                if matched_payload:
                    self.apinext_target.take_screenshot(
                        os.path.join(self.results_dir, f'remove_bt_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
                    )
                    return
            else:
                raise TimeoutError("Failed to remove host bt from IDC23")

    def enter_bt_audio_menu(self):
        """Helper for entering into BT Audio menu"""
        Launcher.go_to_home()
        Media.open_media()
        # If it is not playing bluetooth, then select bluetooth as media source
        if not Media.is_playing_source(self.media_source_name):
            # Select bluetooth as media source
            Media.select_audio_source(Media.MEDIA_BLUETOOTH_SOURCE_ID)
            assert Media.is_playing_source(self.media_source_name), "Failed to select bluetooth as playing source"


class PhoneSimuCommHandler(threading.Thread):  # pylint: disable=too-many-instance-attributes
    """Threaded Class for handling connections with phonesimu service
    A set of callback regex are compiled corresponding to the data output
    by the service on it's telnet interface.
    This thread provides an easy and clean mechanism to parse and extract
    the meaningful data from the service while at the same time sending data
    back to the service to perform further operations.
    Use the PhoneSimuHandler class below to make use of this comm handler instead
    of invoking this class directly.
    """

    READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR
    READ_WRITE = READ_ONLY | select.POLLOUT

    def __init__(self, connections, data_lock, data, audio_logfile=None):
        """Instantiation operator
        :param list: A list of tuples with three elements in each tuple
        tuple:(<name of connection>(str), <socket obj for the connection>, <queue obj for the connection>)
        :param thread lock: A thread lock object for synchronization
        :param dict: A dictionary object for communicating data to consumer/producer
        """
        threading.Thread.__init__(self)
        self.poller = select.poll()
        self.fd_to_sock_conn_name = {}
        self.conn_name_to_msg_queue = {}
        self.conn_recv_buffers = {}
        self.stop_request = threading.Event()
        self.data = data
        self.data_lock = data_lock
        self.audio_logfile = audio_logfile

        for name, sock, que in connections:
            self.poller.register(sock, self.READ_WRITE)
            self.fd_to_sock_conn_name.update({sock.fileno(): (sock, name)})
            self.conn_name_to_msg_queue.update({name: que})
            self.conn_recv_buffers.update({name: bytes()})

        self._callbacks = {
            re.compile(
                r".*alsa-micro-analysis signal-analysis (\d+) (\d+) "
                r"([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+)"
            ): self.callback_measure,
            re.compile(
                r".*sco-audio-analysis signal-analysis (\d+) (\d+) "
                r"([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+) "
                r"([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+)"
            ): self.callback_sco_measure,
            re.compile(r".*BT: IND: \+CIEV: 2,(\d).*"): self.callback_call_status,
            re.compile(
                r".*sco-audio signal-parameters (\d+) ([-+]?[0-9]*\.?[0-9]+) ([-+]?[0-9]*\.?[0-9]+).*"
            ): self.callback_sco_parameters,
            re.compile(
                r".*alsa-speaker signal-parameters (\d+) ([-+]?[0-9]*\.?[0-9]+) ([-+]?[0-9]*\.?[0-9]+).*"
            ): self.callback_speaker_parameters,
            re.compile(
                r".*a2dp-source signal-parameters (\d+) ([-+]?[0-9]*\.?[0-9]+) ([-+]?[0-9]*\.?[0-9]+).*"
            ): self.callback_a2dp_parameters,
            re.compile(r".*PLAY: STATUS: MODE: (\w+)\s*"): self.callback_avrcp_status,
            re.compile(r".* playback-status .*"): self.callback_playback_status,
            re.compile(r".*TST: HF: Connected to (.*)\s*"): self.callback_connection_status,
            re.compile(r".*PLAY: CT: Connected to (.*)\s*"): self.callback_avrcp_connection_status,
        }

    def process_message(self, message):
        """
        This method checks if we received meaningful data
        from phonesimu service. If yes, then call the corresponding
        callback to extract and communicate this new data
        """
        for regexp, callback in self._callbacks.items():
            match = regexp.match(message)
            if match:
                callback(match)
                break

    def process_buffer(self, conn_name):
        """
        Maintain buffers against each connection, since messages can
        come in multiple segments. Construct one entire message and
        call process_message to process it.
        """
        while True:
            index = self.conn_recv_buffers[conn_name].find(END_OF_LINE)
            if index < 0:
                break
            try:
                message = self.conn_recv_buffers[conn_name][:index].decode("utf-8")
                if message.startswith(">"):
                    message = message[1:]
                message = message.strip()
                if message:
                    if self.audio_logfile and conn_name == CONN_AUDIO:
                        self.audio_logfile.write(" ".join([time.asctime(time.localtime()), message + "\n"]))
                    self.process_message(message)
            except UnicodeDecodeError:
                logger.error(f"Application {conn_name} sent invalid data")
            self.conn_recv_buffers[conn_name] = self.conn_recv_buffers[conn_name][
                index + len(END_OF_LINE) :  # noqa: E203
            ]

    def run(self):
        while not self.stop_request.is_set():
            event = self.poller.poll(POLL_TIMEOUT)
            for sock_no, flag in event:
                if flag & (select.POLLIN | select.POLLPRI):
                    sock, conn_name = self.fd_to_sock_conn_name[sock_no]
                    data = sock.recv(2048)
                    if data:
                        self.conn_recv_buffers[conn_name] += data
                        self.process_buffer(conn_name)
                    else:
                        logger.error(f"Application {conn_name} has closed connection unexpectedly")
                        self.poller.unregister(sock)
                        del self.fd_to_sock_conn_name[sock_no]
                elif flag & select.POLLHUP:
                    # Other End hung up
                    # Stop listening for input on the connection
                    sock, conn_name = self.fd_to_sock_conn_name.pop(sock_no)
                    logger.debug(f"Application {conn_name} has hung up", conn_name)
                    self.poller.unregister(sock)
                elif flag & select.POLLOUT:
                    # Socket is ready to send data, if there is any to send.
                    next_msg = ""
                    sock, conn_name = self.fd_to_sock_conn_name[sock_no]
                    msg_queue = self.conn_name_to_msg_queue[conn_name]
                    if not msg_queue.empty():
                        try:
                            next_msg = msg_queue.get_nowait()
                        except queue.Empty:
                            logger.debug(f"Nothing to Send to {conn_name}")
                        if next_msg:
                            logger.info(f"Sending to {conn_name}:{next_msg}\n")
                            sock.send(next_msg)
                elif flag & select.POLLERR:
                    sock, conn_name = self.fd_to_sock_conn_name.pop(sock_no)
                    logger.error(f"On Conn:{conn_name} handling exceptional condition for {sock.getpeername()}")
                    # Stop listening for input on the connection
                    self.poller.unregister(sock)

    def callback_measure(self, rematch):
        count = int(rematch.group(2))
        if count >= INST_FREQ_MEASURE:
            # Instantaenous measure
            frequency = float(rematch.group(4))
            strength = float(rematch.group(5))
            with self.data_lock:
                if frequency != self.data["micro"]["frequency"] and strength > MIN_DETECTION_STRENGTH:
                    self.data["micro"]["time"] = float(rematch.group(1)) * 1e-9
                    self.data["micro"]["frequency"] = frequency
                    self.data["micro"]["updated"] = True
            logger.debug(f"MICRO Recorded frequency {frequency} Hz strength {strength}")
        elif count >= LONG_FREQ_MEASURE:
            # Long duration measure
            logger.debug("MICRO long duration Measure")
            logger.debug(rematch.group(0).strip())

    def callback_sco_measure(self, rematch):
        count = int(rematch.group(2))
        if count >= INST_FREQ_MEASURE:
            # Instantaenous measure
            frequency = float(rematch.group(4))
            strength = float(rematch.group(5))
            with self.data_lock:
                if frequency != self.data["sco"]["frequency"] and strength > MIN_DETECTION_STRENGTH:
                    self.data["sco"]["time"] = float(rematch.group(1)) * 1e-9
                    self.data["sco"]["frequency"] = frequency
                    self.data["sco"]["updated"] = True
            logger.debug(f'SCO frequency {frequency} Hz strength {strength} Updated:{self.data["sco"]["updated"]}')

    def callback_sco_parameters(self, rematch):
        frequency = float(rematch.group(3))
        with self.data_lock:
            if frequency != self.data["phone"]["frequency"]:
                self.data["phone"]["time"] = float(rematch.group(1)) * 1e-9
                self.data["phone"]["frequency"] = frequency

        logger.debug(rematch.group(0).strip())

    def callback_speaker_parameters(self, rematch):
        frequency = float(rematch.group(3))
        with self.data_lock:
            if frequency != self.data["speaker"]["frequency"]:
                self.data["speaker"]["time"] = float(rematch.group(1)) * 1e-9
                self.data["speaker"]["frequency"] = frequency

        logger.debug(rematch.group(0).strip())

    def callback_a2dp_parameters(self, rematch):
        frequency = float(rematch.group(3))
        with self.data_lock:
            if frequency != self.data["entertainment"]["frequency"]:
                self.data["entertainment"]["time"] = float(rematch.group(1)) * 1e-9
                self.data["entertainment"]["frequency"] = frequency

        logger.debug(rematch.group(0).strip())

    def callback_call_status(self, rematch):
        logger.debug(f"Phone status = {rematch.group(1)}")
        with self.data_lock:
            self.data["phone"]["status"] = rematch.group(1)
            self.data["phone"]["updated"] = True

    def callback_avrcp_status(self, rematch):
        avrcp_status = rematch.group(1).strip()
        logger.debug(f"AVRCP status = {avrcp_status}")
        with self.data_lock:
            self.data["avrcp"]["status"] = avrcp_status
            self.data["avrcp"]["updated"] = True

    def callback_connection_status(self, rematch):
        with self.data_lock:
            self.data["hfp_cli_addr"] = rematch.group(1).strip()

    def callback_avrcp_connection_status(self, rematch):
        with self.data_lock:
            self.data["avrcp"]["addr"] = rematch.group(1).strip()

    def callback_playback_status(self, rematch):
        logger.debug(rematch.group(0).strip())


class PhoneSimuHandler(object):
    """Handler Class for managing connections with phonesimu service
    Starts a thread in the background to communicate with phonesimu service.
    This class is responsible for managing the communicator thread.
    It provides an interface to the consumer to easily communicate with
    phonesimu services.
    """

    def __init__(self, connections, log_file_path=None):
        """Instantiation Operator
        :param list: A list of tuples with two elements in each tuple
        tuple:(<name of connection>(str), <socket obj for the connection>)
        :param string: A string containing the path for audio signal telnet logs
        """
        self._msg_queues = {}
        self._connections = []
        self._log_fh = None
        self._started = False
        self._audio_sock = None
        self._phonesimu_data_state = {
            "micro": {"frequency": 0, "time": 0, "updated": False},
            "sco": {"frequency": 0, "time": 0, "updated": False},
            "phone": {"frequency": 0, "time": 0, "status": "", "updated": False},
            "speaker": {"frequency": 0, "time": 0},
            "entertainment": {"frequency": 0, "time": 0},
            "avrcp": {"status": "", "addr": "", "updated": False},
            "hfp_cli_addr": "",
        }
        self._data_lock = threading.Lock()
        for name, sock in connections:
            if name == CONN_AUDIO:
                self._audio_sock = sock
            self._msg_queues.update({name: queue.Queue()})
            self._connections.append((name, sock, self._msg_queues[name]))
        if log_file_path:
            try:
                self._log_fh = open(log_file_path, "w")
            except IOError:
                raise IOError("PhoneSimuHandler Failed to open audio_signal_telnet prompt log file")
        self.comm_handler = PhoneSimuCommHandler(
            self._connections, self._data_lock, self._phonesimu_data_state, self._log_fh
        )
        self._set_alsa_mixer_config()

    def _set_alsa_mixer_config(self):
        subprocess.run(["amixer", "-D", "default", "set", "Mic", "80%"])
        subprocess.run(["amixer", "-D", "default", "set", "PCM", "80%"])
        subprocess.run(["amixer", "-D", "default", "set", "AUto Gain Control", "Disabled"])

    def start_comm(self):
        self.comm_handler.start()
        self._started = True

    def get_data(self, refresh=True):
        """Getter for phonesimu_data_state dict.
        Returns a deep copy of the dict so that the consumer
        does not get a reference back to the original data
        structure or recursively any internal data structures
        held by it.
        :param boolean refresh: if false we do not care about updating the updated flags
        """
        if not self.comm_handler.is_alive():
            self._log_fh.close()
            raise AssertionError(
                "phonesimu comm handler is dead. Ending Blue Tooth Endurance Test"
                if self._started
                else "[get_data] called before starting comm handler[start_comm]"
            )
        with self._data_lock:
            latest_data = copy.deepcopy(self._phonesimu_data_state)
            if refresh:
                for data_element in self._phonesimu_data_state.values():
                    if isinstance(data_element, dict) and "updated" in data_element:
                        data_element["updated"] = False

        return latest_data

    def send_data(self, conn_name, data):
        if not self.comm_handler.is_alive():
            self._log_fh.close()
            raise AssertionError(
                "phonesimu comm handler is dead. Ending Blue Tooth Endurance Test"
                if self._started
                else "[send_data] called before starting comm handler[start_comm]"
            )
        msg_queue = self._msg_queues[conn_name]
        msg_queue.put(data)

    def stop_comm(self):
        self.comm_handler.stop_request.set()
        self.comm_handler.join()
        self._log_fh.close()
        self._started = False
        self._audio_sock.close()
