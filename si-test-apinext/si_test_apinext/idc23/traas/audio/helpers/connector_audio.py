# Copyright (C) 2022. BMW CTW. All rights reserved.
"""Audio connector class"""

from collections import namedtuple
import glob
import logging
import os
import pathlib
from queue import Empty, Queue
import re
import select
import socket
import telnetlib
import threading
import time

import matplotlib.pyplot as plot
from mtee.testing.connectors.connector_base import Connector
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import retry_on_except, run_command, TimeoutCondition, TimeoutError
import numpy
from pydub import AudioSegment
from scipy.io import wavfile

# Number of consecutive voice frames detected
_VAD_QUALITY_METRIC = 5

# Maximum aplitude level to be considered silence
SILENCE_THRESHOLD = 85  # Value got from experience

logger = logging.getLogger(__name__)


SignalParameters = namedtuple("SignalParameters", ["timestamp", "strength", "main_frequency", "f1", "f2", "f3", "f4"])
"""Parameters of the recorded signal at specific time

.. py:attribute:: timestamp
    Capture time in nanoseconds

.. py:attribute:: strength
    Signal's strength from 0 to 1

.. py:attribute:: main_frequency
    Tuple of (frequency of main harmonic, main harmonic's strength)

.. py:attribute:: f1
    Tuple describing frequency #1 (frequency, strength)

.. py:attribute:: f2
    Tuple describing frequency #2 (frequency, strength)

.. py:attribute:: f3
    Tuple describing frequency #3 (frequency, strength)

.. py:attribute:: f4
    Tuple describing frequency #4 (frequency, strength)
"""

VADParameters = namedtuple("VADParameters", ["timestamp", "r1", "r2", "decision", "simi"])
"""Voice audio detection parameters of the recorded signal at specific time

.. py:attribute:: timestamp
    Capture time in nanoseconds

.. py:attribute:: r1
    First VAD ratio, floating point number

.. py:attribute:: r2
    Second VAD ratio, floating point number

.. py:attribute:: decision
    String characterizing audio for this frame, voice/silence/noise

.. py:attribute:: simi
    Running count representing similarity of current frame with the previous frame

"""

# phonesimu telnet address and port
_PHONESIMU_AUDIO_APP_ADDR = "127.0.0.1"
_PHONESIMU_AUDIO_APP_PORT = 3000


class PhoneSimuReader(threading.Thread):
    """Thread object to read stdout from the phonesimu's telnet connection"""

    # we are interested only in lines with number of harmonics = 513 (reasonable FFT precision)
    freq_re_string = (
        r"^alsa-micro-analysis\ssignal-analysis\s(?P<timestamp>\d+)\s513\s"
        r"(?P<strength>\d+\.\d+)\s"
        r"(?P<main_frequency>\d+\.\d+:\d+\.\d+)\s"
        r"(?P<f1>\d+\.\d+:\d+\.\d+)\s"
        r"(?P<f2>\d+\.\d+:\d+\.\d+)\s"
        r"(?P<f3>\d+\.\d+:\d+\.\d+)\s"
        r"(?P<f4>\d+\.\d+:\d+\.\d+)\s*$"
    )

    vad_re_string = (
        r"^alsa-micro-analysis\svad-analysis\s(?P<timestamp>\d+)\s"
        r"VAD1:(?P<r1>\d+\.\d+)\s"
        r"VAD2:(?P<r2>\d+\.\d+)\s"
        r"DECISION:(?P<decision>[a-z]+)\s"
        r"Similarity:(?P<simi>\d+)\s*$"
    )

    def __init__(self, log_filename):
        super(PhoneSimuReader, self).__init__(name="phonesimu reader")
        self._port = _PHONESIMU_AUDIO_APP_PORT
        self._telnet = telnetlib.Telnet()
        self.stop_flag = threading.Event()
        self.vad_queue = Queue()
        self._freq_re = re.compile(self.freq_re_string, re.VERBOSE)
        self._vad_re = re.compile(self.vad_re_string, re.VERBOSE)
        self._log_filename = log_filename
        self.telnet_connected = False
        self.attributes = {"match_params": None}
        try:
            self.start_telnet_session()
        except socket.error:
            self._telnet.close()
            logger.exception("Failed to start telnet connection to phonesimu audio app")

    @property
    def match_params(self):
        """Safeguard match params and alert user"""
        if not self.telnet_connected:
            logger.exception("PhoneSimuReader not connected. match_params is invalid")

        return self.attributes["match_params"]

    @match_params.setter
    def match_params(self, val):
        """Safeguard match params and alert user"""
        if not self.telnet_connected:
            logger.exception("PhoneSimuReader not connected. match_params is invalid")

        self.attributes["match_params"] = val

    def run(self):
        """Main thread worker function"""
        if not self.telnet_connected:
            logger.error("Failed to run PhoneSimuReader. Telnet not connected")
            return
        with open(self._log_filename, "w") as logfile:
            while not self.stop_flag.is_set():
                line = self._telnet.read_until(b"\r\n", timeout=180).decode()
                if line.strip():
                    logfile.write(" ".join([time.asctime(time.localtime()), line]))
                    match = self._freq_re.match(line)
                    match_vad = self._vad_re.match(line)
                    if match:
                        self.match_params = match
                    # In case of matching a vad-analysis line, notify the waiting threads
                    if match_vad:
                        self.vad_queue.put(match_vad)

        if self.telnet_connected:
            self._telnet.close()
            self.telnet_connected = False
            logger.debug("Telnet Connection closed with phonesimu audio app successfully")

    @retry_on_except()
    def start_telnet_session(self):
        """Establish a telnet connection with running phonesimu audio app instance"""
        logger.debug("Trying to establish Telnet connection with phonesimu audio app")

        self._telnet.open("127.0.0.1", self._port, 10)
        # Make sure we have established a stable connection
        if self._telnet.sock:
            for _ in range(5):
                # pylint 1.8.3 reports error, but pylint 1.9.5 in mtee_core does not, for similar usage
                # in vcar_manager (sock.send)
                self._telnet.sock.send(telnetlib.IAC + telnetlib.NOP)  # pylint: disable=no-member
                time.sleep(0.1)
            logger.debug("Telnet Connection with phonesimu audio app established successfully")
            self.telnet_connected = True
        else:
            raise socket.error()


class PhoneSimuSockHandler(threading.Thread):
    """Thread object to handle communication with PhoneSimu's telnet connection"""

    READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR
    READ_WRITE = READ_ONLY | select.POLLOUT
    POLL_TIMEOUT = 100

    def __init__(self, output_queue, sock):
        threading.Thread.__init__(self)
        self.msg_queue = output_queue
        self.poller = select.poll()
        self.stop_request = threading.Event()
        self.sock = sock
        self.poller.register(sock, self.READ_WRITE)

    def run(self):
        while not self.stop_request.is_set():
            event = self.poller.poll(self.POLL_TIMEOUT)
            for _, flag in event:
                if flag & (select.POLLIN | select.POLLPRI):
                    data = self.sock.recv(2048)
                    if not data:
                        logger.exception("phonesimu Audio Signal has unexpectedly closed connection")
                        self.poller.unregister(self.sock)
                elif flag & select.POLLHUP:
                    # Other End hung up
                    # Stop listening for input on the connection
                    logger.exception("phonesimu Audio Signal has unexpectedly closed connection")
                    self.poller.unregister(self.sock)
                elif flag & select.POLLOUT:
                    # Socket is ready to send data, if there is any to send.
                    next_msg = ""
                    if not self.msg_queue.empty():
                        try:
                            next_msg = self.msg_queue.get_nowait()
                        except Empty:
                            pass
                        if next_msg:
                            self.sock.send(next_msg.encode())
                elif flag & select.POLLERR:
                    logger.exception("Exceptional condition for phonesimu Audio Signal connection occurred")
                    # Stop listening for input on the connection
                    self.poller.unregister(self.sock)


class ConnectorAudio(Connector):
    """Audio connector"""

    priority = -1

    def __init__(self, test):
        """Initialize the ConnectorAudio object"""
        self.result_dir = test.results_dir
        self._sock = None
        self._reader = None
        self._recording_state = False
        self._start_recording = False
        self._context = "audio_conn"
        self._output_queue = Queue()
        self._sock_handler = None
        self._recording_path = None

    def __call__(self, context, record):
        """Parameterize the ConnectorAudio object

        :param context string: recording and log files will be appended with this string
        :param record bool: Audio recording will be started when this flag is set to True
        """
        self._start_recording = record
        self._context = context
        return self

    def __enter__(self):
        """Enter context. Open telnet connection to phonesimu"""
        logger.debug("AudioContext entered")

        logfile_path = os.path.join(self.result_dir, "phonesimu-log-files")
        if not os.path.exists(logfile_path):
            logger.debug("Creating recordings directory '%s'", logfile_path)
            os.makedirs(logfile_path)
        else:
            logger.debug("Log file directory exists: '%s'", logfile_path)

        logfilename = self._context + "_phonesimu_reader_" + time.strftime("%Y%h%d_%H-%M-%S") + ".log"
        self._reader = PhoneSimuReader(os.path.join(logfile_path, logfilename))
        if not self._reader.telnet_connected:
            logger.exception("phonesimureader failure, cannot connect to phonesimu phone app")

        self._reader.start()
        if self._start_recording:
            self.start_recording(self._context + "_recording")

        return self

    def wait_for(self, attrs, timeout=30):
        """Wait until signal with specific parameters occurs

        :param dict attrs: Dictionary of attributes and compare functions
            {"strength": cmp_func, "main_frequency": cmp_func2}. Method returns matching SignalParameters object
        :param float timeout: Timeout for message receiving. Defaults to 30s
        :returns: matching SignalParameters object if frequency is found, otherwise return None
        :rtype: SignalParameters or None
        """
        logger.info("Waiting %ds for signal %s", timeout, attrs)
        timeout_condition = TimeoutCondition(timeout)

        try:
            while timeout_condition():
                params = self._reader.match_params
                if params:
                    all_match = True
                    params = params.groupdict()
                    for key, cmp_func in attrs.items():
                        if not cmp_func(params[key]):
                            all_match = False
                            break

                    if all_match:
                        logger.info(" Signal detected after %fs", timeout_condition.time_elapsed)
                        return self._parse_signal_parameters(params)

                time.sleep(0.1)
        except TimeoutError:
            return None

    def wait_for_silence(self, consecutive_matches=5, timeout=30):
        """
        Wait until silence is detected

        :param int consecutive_matches: Number of consecutive frames to be detected with silence. Defaults to 15
        :param float timeout: Total test maximum time. Defaults to 30s

        :returns: True if silence was detected for 'consecutive_matches' frames, if not return False
        """
        logger.info("Waiting %ds for silence", timeout)
        timeout_condition = TimeoutCondition(timeout)

        match_count = 0
        prev_timestamp = 0

        try:
            while timeout_condition():
                try:
                    # Non-Blocking call with timeout 1 second to get matching
                    # VAD line from queue
                    params = self._reader.vad_queue.get(False, 1)
                    params = params.groupdict()
                    decision = params["decision"]
                    if decision == "silence":
                        # We would like to match consecutive audio frames with
                        # lowest similarity
                        if int(params["timestamp"]) != prev_timestamp:
                            match_count += 1
                            prev_timestamp = int(params["timestamp"])
                        else:
                            logger.warning("Matched same VAD line again!")
                    else:
                        logger.info(f"Detected '{decision}'! Resetting match current match count{match_count} to 0")
                        match_count = 0
                    # processing on this VAD analysis line done
                    self._reader.vad_queue.task_done()
                    if match_count >= consecutive_matches:
                        logger.info(
                            "Silence detected in %d consecutive frames, after %ds",
                            consecutive_matches,
                            timeout_condition.time_elapsed,
                        )
                        return True
                except Empty:
                    logger.warning("VAD match not found in the Queue!")
                    # Wait a bit before retrying retrieval from VAD Queue
                    time.sleep(0.1)
        except TimeoutError:
            return False

    def wait_for_voice(self, consecutive_matches=_VAD_QUALITY_METRIC, timeout=30):
        """
        Wait until voice is detected with reasonable confidence

        :param int consecutive_matches: Consecutive voice audio frames to be detected.
            Defaults to current voice quality metric.
        :param float timeout: Timeout for message receiving. Defaults to 30s
        :returns: matching VADParameters object if silence is detected otherwise return None
        :rtype: VADParameters or None
        """
        logger.info("Waiting %ds for voice", timeout)
        timeout_condition = TimeoutCondition(timeout)

        voice_match_count = 0
        prev_timestamp = 0
        try:
            while timeout_condition():
                try:
                    logger.info("Getting VAD match line from Queue")
                    # Non-Blocking call with timeout 1 second to get matching
                    # VAD line from queue
                    params = self._reader.vad_queue.get(False, 1)
                    params = params.groupdict()
                    if params["decision"] == "voice" and int(params["simi"]) == 0:
                        # We would like to match consecutive audio frames with
                        # lowest similarity
                        if int(params["timestamp"]) != prev_timestamp:
                            voice_match_count += 1
                            prev_timestamp = int(params["timestamp"])
                        else:
                            logger.warning("Matched same VAD line again!")
                    else:
                        logger.info("Detected noise, silence or voice with high similarity")
                        voice_match_count = 0
                    # processing on this VAD analysis line done
                    self._reader.vad_queue.task_done()
                    if voice_match_count >= consecutive_matches:
                        logger.info("Voice detected in %d consecutive frames", consecutive_matches)
                        return self._parse_vad_parameters(params)
                except Empty:
                    logger.warning("VAD match not found in the Queue!")
                    # Wait a bit before retrying retrieval from VAD Queue
                    time.sleep(0.1)
        except TimeoutError:
            return None

    def _parse_signal_parameters(self, params):
        """Parse signal parameters into SignalParameters object and convert from strings to numbers"""
        return SignalParameters(
            timestamp=int(params["timestamp"]),
            strength=float(params["strength"]),
            main_frequency=map(float, params["main_frequency"].split(":")),
            f1=map(float, params["f1"].split(":")),
            f2=map(float, params["f2"].split(":")),
            f3=map(float, params["f3"].split(":")),
            f4=map(float, params["f4"].split(":")),
        )

    def _parse_vad_parameters(self, params):
        """Parse voice audio detection parameters into VADParameters object easy to read/view"""
        return VADParameters(
            timestamp=int(params["timestamp"]),
            r1=float(params["r1"]),
            r2=float(params["r2"]),
            decision=params["decision"],
            simi=int(params["simi"]),
        )

    def _clear_vad_queue(self):
        """Empties the vad_queue."""
        while not self._reader.vad_queue.empty():
            try:
                self._reader.vad_queue.get_nowait()
            except Empty:
                continue
            self._reader.vad_queue.task_done()

    @property
    def signal_parameters(self):
        """Return latest signal parameters"""
        params = self._reader.match_params.groupdict()
        return self._parse_signal_parameters(params)

    def get_audio_card_info(self):
        """Return alsa HW info with audio card number"""
        result = run_command(["aplay", "-l"], check=True)
        regex = re.compile(r"card (\d+): .*USB Audio")
        matches = regex.findall(result.stdout)[0]
        logger.info("USB audio card number is: %s", matches)
        return f"hw:{matches},0"  # there is a new usb sound card as default.

    def start_recording(self, prefix="recording"):
        """Start recording and analysing the audio"""
        results_path = os.path.join(self.result_dir, "phonesimu-recordings")
        if not os.path.exists(results_path):
            logger.debug("Creating recordings directory '%s'", results_path)
            os.makedirs(results_path)
        else:
            logger.debug("Recordings directory exists: '%s'", results_path)

        alsa_hw = self.get_audio_card_info()
        self._recording_path = os.path.join(results_path, prefix)
        if not self._recording_state:
            self.send(f"alsa-micro new-alsa-micro {alsa_hw} 48000")
            self.send(f"alsa-micro record {self._recording_path} 0.1")
            self._recording_state = True
            logger.info(
                f"Recording started. path='{self._recording_path}' "
                + "caution: name will be appended with timestamp for uniqueness"
            )
            return True
        logger.warning("There is already an on-going recording, can't start a new one!")
        return False

    def stop_recording(self):
        """Stop recording and analysing audio"""
        self._context = "audio_conn"
        self._start_recording = False

        if self._recording_state:
            self.send("alsa-micro-recorder exit")
            self.send("alsa-micro exit")
            self._recording_state = False
            logger.info("Recording stopped succesfully")
            return True
        logger.warning("No recording on-going, so nothing to stop")
        return False

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context"""
        # stop the reader thread
        self._reader.stop_flag.set()
        logger.debug("Cleaning up VAD Queue")
        self._clear_vad_queue()
        logger.debug("Joining phonesimu reader thread")
        self._reader.join()
        logger.debug("phonesimu reader thread joined")
        self.stop_recording()
        logger.debug("AudioContext left")
        self.generate_audio_analysis(self._recording_path)
        logger.debug("Generated audio analysis")

    def send(self, cmd):
        """Sends command to Audio application profile

        :param string cmd: Command to be sent to Audio application profile
        """
        logger.info("Sending command to Audio application profile: %s", cmd)
        self._output_queue.put(cmd + "\r\n")

    def start(self):
        """Start the audio connector"""
        # Try to connect to audio app of phonesimu, continue the MTEE even if it fails
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.connect((_PHONESIMU_AUDIO_APP_ADDR, _PHONESIMU_AUDIO_APP_PORT))
            if self._sock:
                self._sock_handler = PhoneSimuSockHandler(self._output_queue, self._sock)
                self._sock_handler.start()
            return TE.feature.audio
        except socket.error:
            self._sock.close()
            self._sock = None
            logger.exception("Failed to start the ConnectorAudio")
            return None

    def stop(self):
        """Stop connector loop"""
        if self._sock_handler:
            self._sock_handler.stop_request.set()
            self._sock_handler.join()
            self._sock.close()
            self._sock = None

    def generate_audio_analysis(self, audio_file):
        """
        Generate a image file with amplitude and frequency analysis of audio file

        :param audio_file: path to audio file
        :type audio_file: str
        :raises AssertionError: If more than one file found
        """
        audio_files = [file for file in glob.glob(f"{audio_file}*.wav")]
        if len(audio_files) != 1:
            raise AssertionError(f"Expected 1 but found {len(audio_files)} files: '{audio_files}'")

        audio_file = audio_files[0]

        # Get audio file name
        image_name = pathlib.Path(audio_file).stem
        # Create results folder
        parent = pathlib.Path(audio_file).parent
        results_folder = os.path.join(parent, "audio_analysis")
        if not os.path.exists(results_folder):
            os.mkdir(results_folder)
        # Final image name
        filename = os.path.join(results_folder, image_name + ".png")

        # Create mono audio files folder folder
        monos_folder = os.path.join(parent, "converted_mono")
        if not os.path.exists(monos_folder):
            os.mkdir(monos_folder)
        # Create a mono file from the stereo file
        final_audio_name = image_name + "_MONO" + "_test.wav"
        final_audio_name = os.path.join(parent, monos_folder, final_audio_name)
        sound = AudioSegment.from_file(audio_file)
        sound = sound.set_channels(1)
        sound.export(final_audio_name, format="wav")
        audio_file = final_audio_name

        sampling_freq, signal_data = wavfile.read(audio_file)
        sample_pts = float(signal_data.shape[0])
        time_array = numpy.arange(0, sample_pts, 1)
        time_array = time_array / sampling_freq

        max_abs = max(max(signal_data), abs(min(signal_data)))

        plot.subplot(211)
        plot.plot(time_array, signal_data)
        plot.axhline(y=SILENCE_THRESHOLD, color="r", linestyle="dashed", label="Silence threshold")
        plot.axhline(y=-SILENCE_THRESHOLD, color="r", linestyle="dashed", label="Silence threshold")
        plot.legend((f"Amplitude (abs max: {max_abs})", f"Silence threshold: {SILENCE_THRESHOLD}"))
        plot.title(f"Amp and Freq of {image_name}")
        plot.ylabel("Amplitude")
        plot.subplot(212)
        plot.ylabel("Frequency [Hz]")
        plot.xlabel("Time [sec]")
        plot.specgram(signal_data, Fs=sampling_freq)
        plot.savefig(filename, bbox_inches="tight")
        plot.clf()
