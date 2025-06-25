# Copyright (C) 2022. BMW CTW. All rights reserved.
"""Base class for audio analysis helper functions"""
import glob
import logging
import time

from pydub import AudioSegment

from .connector_audio import ConnectorAudio, SILENCE_THRESHOLD

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CompareMinStrength(object):
    """This class is to be used as compare function for checking if the given number (strength)
    is higher then given threshold"""

    def __init__(self, min_strength=0.4):
        self._min_strength = float(min_strength)

    def __call__(self, value):
        """call the instantiated object as a function

        :param string/number value: A strength (amplitude) of the signal
        :returns bool: True if the number is higher then threshold
        """
        return self._min_strength <= float(value)

    def __repr__(self):
        return "cmp_min_strength(>{})".format(self._min_strength)


class CompareFrequency(object):
    """This class is to be used as compare function for checking if the given number (frequency)
    fits into given interval"""

    def __init__(self, ref_freq, deviation=20):
        self._ref_freq = ref_freq
        self._deviation = deviation

    def __call__(self, value):
        """call the instantiated object as a function

        :param string value: A pair of frequency and it's strength (amplitude) eg. "405.544:0.3054"
        :returns bool: True if the number fits into the interval <ref_req += deviation>
        """
        return (self._ref_freq - self._deviation) < float(value.split(":")[0]) < (self._ref_freq + self._deviation)

    def __repr__(self):
        return "cmp_freq({}<, >{})".format(self._ref_freq - self._deviation, self._ref_freq + self._deviation)


class AudioAnalyzer(object):
    """Audio signal analyzer."""

    def __init__(self, test):
        """Audio Analyzer"""
        self.connector_audio = ConnectorAudio(test)

    # pylint: disable=too-many-arguments
    def check_frequency(
        self, frequency, frequency_deviation, context, timeout, post_record_duration=2.0, min_strength=0.4
    ):
        """Check if expected frequency is detected

        :param frequency: expected frequency
        :type frequency: int
        :param frequency_deviation: acceptable deviation
        :type frequency_deviation: int
        :param context: name for audio recording
        :type context: str
        :param timeout: timeout waiting for frequency to be detected
        :type timeout: int
        :param post_record_duration: additional recording time, defaults to 2.0 seconds
        :type post_record_duration: float, optional
        :param min_strength: minimum acceptable frequency strength, defaults to 0.4
        :type min_strength: float, optional

        :return: SignalParameters if voice is detected, otherwise return None
        :rtype: SignalParameters or None
        """
        with self.connector_audio(context=context, record=True) as audio:
            analyses = audio.wait_for(
                attrs={
                    "strength": CompareMinStrength(min_strength),
                    "main_frequency": CompareFrequency(frequency, frequency_deviation),
                },
                timeout=timeout,
            )
            time.sleep(post_record_duration)  # Additional recording if signal is detected too early
            return analyses

    def check_silence(self, context="check_silence", consecutive_matches=10, timeout=30):
        """
        Connector audio wrapper function to wait for silence and return result

        :param context: name for audio recording, defaults to "check_silence"
        :type context: str, optional
        :param consecutive_matches: Number of consecutive frames to be detected with silence, defaults to 15
        :type consecutive_matches: int, optional
        :param timeout: Total test maximum time, defaults to 30
        :type timeout: int, optional
        :return: True if silence was detected for 'consecutive_matches' frames, if not return False
        :rtype: bool
        """
        with self.connector_audio(context=context, record=True) as audio:
            # Wait for silence detection
            result_check_silence = audio.wait_for_silence(consecutive_matches=consecutive_matches, timeout=timeout)
            return result_check_silence

    def check_voice_detection(self, context, consecutive_matches=5, timeout=60, post_record_duration=2.0):
        """
        Check if voice is detected

        :param context: name for audio recording
        :type context: str
        :param consecutive_matches: Number of consecutive frames to be detected as voice, defaults to 5
        :type consecutive_matches: int, optional
        :param timeout: timeout waiting for voice to be detected, defaults to 60
        :type timeout: int, optional
        :param post_record_duration: additional recording time, defaults to 2.0 seconds
        :type post_record_duration: float, optional

        :return: VAD parameters if voice is detected, otherwise return None
        :rtype: VADParameters or None
        """
        with self.connector_audio(context=context, record=True) as audio:
            analyses = audio.wait_for_voice(consecutive_matches=consecutive_matches, timeout=timeout)
            time.sleep(post_record_duration)
            return analyses

    def record_audio_sample(self, context, duration=10):
        """
        Record a audio file with worker mic
        :param context: name for audio recording
        :type context: str
        :param duration: recording time, defaults to 10 sec
        :type duration: int, optional
        :raises RuntimeError: Raised in case of any recording failure
        :return: Path to recorded file
        :rtype: str
        """
        with self.connector_audio(context=context, record=True) as audio:
            time.sleep(duration)
            return audio._recording_path

    def verify_silence(self, context, duration=10, silence_tresh=SILENCE_THRESHOLD):
        """
        Analyze audio file maximum amplitude and decide if file only contains silence

        :param context: name for audio sample to be recorded
        :type context: str
        :param duration: duration of sample to be recorded, defaults to 10
        :type duration: int, optional
        :param silence_tresh: value for maximum amplitude allowed for silence, defaults to SILENCE_THRESHOLD
        :type silence_tresh: int, optional
        :raises AssertionError: When more than one file is found
        :return: True if audio sample only has silence
        :rtype: bool
        """
        result_path = self.record_audio_sample(context=context, duration=duration)
        logger.info(f"Recorded this audio file: '{result_path}'")

        audio_files = [file for file in glob.glob(f"{result_path}*.wav")]
        if len(audio_files) != 1:
            raise AssertionError(f"More than one audio file found: '{audio_files}'")

        # reading from audio wav file
        sound = AudioSegment.from_file(audio_files[0], "wav")
        # remove the first 2 seconds
        two_seconds = 2 * 1000
        sound_trimmed = sound[two_seconds:]

        peak_amplitude = sound_trimmed.max
        # Decide silence (True) if the peak amplitude on the recorded audio file doesn't exceed the threshold
        decision_silence = True if peak_amplitude <= silence_tresh else False
        logger.info(
            f"Analyzing silence on audio file: '{audio_files[0]}' "
            f"Max amplitude:'{peak_amplitude}', Found silence: {decision_silence}"
        )

        return decision_silence
