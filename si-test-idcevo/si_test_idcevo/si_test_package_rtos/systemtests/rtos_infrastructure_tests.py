# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""RTOS infrastructure"""
import configparser
import logging
import os
import re
import shutil
import time
from pathlib import Path
from unittest import SkipTest, skip, skipIf

from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import (
    assert_equal,
    assert_process_returncode,
    assert_true,
    metadata,
    run_command,
)
from mtee.tools.nose_parametrize import nose_parametrize

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.dmverity_helpers import execute_cmd_and_validate, validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.reboot_handlers import reboot_and_wait_for_android_target
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, set_service_pack_value

from tee.tools.lifecycle import LifecycleFunctions
from tee.tools.utils import with_uploaded_file
from validation_utils.utils import TimeoutError

# Config parser reading data from config file.
config = configparser.ConfigParser()

config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

target = TargetShare().target
lf = LifecycleFunctions()

GET_SENSOR_TEMP_PATTERN = re.compile(r".*sensor.*(\d).*has\s*(\d*)\s*C*")
# The following regex pattern matches any string that contains
# and ends with "sensor (X)", where X is an integer.
NO_SENSOR_DATA_PATTERN = re.compile(r".*sensor\s*\(\s*(\d+)\s*\)\s*$")
SOC_SENT_PACKETS = re.compile(r".*Listen test, sent .* (\d+).*", re.IGNORECASE)
SENSORS_DATA = {
    0: {
        "name": "SENSOR_AMBIENT",
        "min": -40,
        "max": 99,
    },
    1: {
        "name": "SENSOR_UFS",
        "min": -40,
        "max": 99,
    },
    2: {
        "name": "SENSOR_ETH",
        "min": -40,
        "max": 104,
    },
    3: {
        "name": "SENSOR_SOC",
        "min": -40,
        "max": 122,
    },
}

EXPECTED_IPCDEBUG_CONTENT = [f"CH{i:02d}" for i in range(1, 32)]
EXPECTED_IPC_CHANNELS = [f"/dev/ipc{i}" for i in range(1, 32)]
EXPECTED_IPC_CHANNELS.append("/dev/ipcdebug")

IOC_DATA_MSGS = [
    re.compile(r"\[SW_VER\] PBL:\[ (\d+ . \d+ . \d+) \]"),
    re.compile(r"\[SW_VER\] SBL:\[ (\d+ . \d+ . \d+) \]"),
    re.compile(r"\[SW_VER\] APP:\[ (\d+ . \d+ . \d+) \]"),
]
IOC_SENT_PACKETS = re.compile(r".*MCU listen test: received .* (\d+).*")

VERSION_DLT_PATTERN = re.compile(r":\[(.+?)\]")
COMPONENT_DLT_PATTERN = re.compile(r"\[SW_VER\] (.+?):\[")

VERSION_TERMINAL_PATTERN = re.compile(r"\d+.\d+.\d+")
COMPONENT_TERMINAL_PATTERN = re.compile(r"readIOCVersion\(\) (.+?) version")

required_target_packages = ["hdlc"]
PACKETS = [
    (2, 100),
    (10, 10),
    (100, 1),
]

IMAGE_DIR = "/images"
MCU_BINS = "/images/mcu/MCU_Binaries.zip"
MCU_BINS_SYS = str(Path(IMAGE_DIR) / "MCU_Binaries.zip")
MCU_FLASH_UPDATE_EXPECTED = [
    re.compile(r"readUpdateImage\(\)"),
    re.compile(r"Passive SBL : [1|2]"),
    re.compile(r"Passive APP : [3|4]"),
    re.compile(r"PARTITIONS ACTIVATION SUCCESSFUL"),
    re.compile(r"FLASHING DONE"),
    re.compile(r"RESTART THE DEVICE"),
]

MCU_COMMON_PATTERNS_ON_REBOOT = [
    {"payload_decoded": re.compile(r".*System has been started.*")},
    {"payload_decoded": re.compile(r".*Waiting for current voltage level to receive (\d+).(\d+)V.*")},
    {"payload_decoded": re.compile(r".*Current voltage level is ready to continue startup sequence.*")},
    {"payload_decoded": re.compile(r".*SOC boot flags:.*SOC active partition.*(\d).*")},
    {"payload_decoded": re.compile(r".*SFI and MCU boot flags:.*SFI boot type.*[(\d+)=UFS, (\d+)=NOR].*")},
    {"payload_decoded": re.compile(r".*SoC to be ready.*")},
    {"payload_decoded": re.compile(r".*SoC is ready.*")},
    {"payload_decoded": re.compile(r".*Set baudrate to  1000000  for SFI port.*")},
    {"payload_decoded": re.compile(r".*Set baudrate to  1000000  for NODE0 port.*")},
    {"payload_decoded": re.compile(r".*Set baudrate to  4000000  for NODE0 port.*")},
    {"payload_decoded": re.compile(r".*\[SWDL_IPC] IOC channel to NODE0 for MCU SWDL opened successfully.*")},
    {"payload_decoded": re.compile(r".*\[SWDL_SOC] IOC channel to NODE0 for SOC SWDL opened successfully.*")},
]

MCU_PATTERNS_ON_REBOOT = {
    "idcevo": {
        "SP21": [
            *MCU_COMMON_PATTERNS_ON_REBOOT,
            {"payload_decoded": re.compile(r".*INIT: Recognized RCM Power On Reset Source.*")},
            {"payload_decoded": re.compile(r".*IOC channel to NODE0 opened successfully.*")},
        ],
        "SP25": [
            *MCU_COMMON_PATTERNS_ON_REBOOT,
            {"payload_decoded": re.compile(r".*INIT: Recognized RCM Power On Reset Source.*")},
        ],
    },
}

MCU_PAYLOAD_TIMEOUT = 60
SOC_PAYLOAD_TIMEOUT = 60
MCU_PAYLOAD = re.compile(r".*Current lifecycle number .* (\d+).*")
SOC_PAYLOAD = re.compile(r".*setLifecycleCounter\((\d+)\).*")

MCU_ETH_WUP_PULSE_FILTER = [
    *MCU_COMMON_PATTERNS_ON_REBOOT,
    {"payload_decoded": re.compile(r".*Switch to VLPS mode initiated.*")},
]
MCU_SLEEP_CMD = "nsg_control --r 0"


class TestsRTOSInfrastructure(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        cls.hw_model = cls.test.mtee_target.options.target
        cls.service_pack = set_service_pack_value()
        cls.ver_gen_path = "/images/mcu/ver_gen.txt"
        cls.target_name = cls.test.mtee_target.options.target

        if not cls.test.mtee_target.connectors.ioc_dlt.broker.isAlive():
            cls.test.mtee_target.connectors.ioc_dlt.start()

        cls.ipk_checked = check_ipk_installed(required_target_packages)

    def validate_ipc_channels_output(self, expected_pattern, obtained_output):
        """Verifies if all expected patterns are obtained for a given ipc test command

        :param expected_pattern: list containing the expected regex patterns
        :param obtained_output: list containing the obtained output

        :return list_patterns_found: list conining the expected regex patterns found
        """
        list_patterns_found = []
        for raw_pattern in expected_pattern:
            pattern = re.compile(raw_pattern)
            if any(pattern.search(line) for line in obtained_output):
                list_patterns_found.append(raw_pattern)
        return list_patterns_found

    def remove_non_ascii_characters(self, input_string):
        """Removes non ASCII characteres.
        Filters out characters with ASCII values greater than or equal to 128.
        """
        return "".join(char for char in input_string if ord(char) < 128)

    def get_ioc_versions_from_dlt_msgs(self, dlt_msgs):
        """Parsing messages found on DLT to retrieve all versions required

        :param dlt_msgs: Messages found on DLT
        :type dlt_msgs: Array of strings
        :return: Dict with IOC component and corresponding version.
        :rtype: Dict
        """
        versions_dlt_list = {}
        for msg in dlt_msgs:
            version_decoded = re.search(VERSION_DLT_PATTERN, msg)
            component_decoded = re.search(COMPONENT_DLT_PATTERN, msg)
            if version_decoded and component_decoded:
                version_decoded_parsed = version_decoded.group(1).replace(" ", "")
                component_decoded_parsed = component_decoded.group(1).replace(" ", "")
                versions_dlt_list[component_decoded_parsed] = version_decoded_parsed
        return versions_dlt_list

    def get_ioc_versions_from_soc_terminal_msgs(self, terminal_msgs):
        """Parse IOC version from SOC terminal obtained output

        :param terminal_msgs: Output of "iocUpdateUtility -v" command
        :type terminal_msgs: Array
        :return: Dict with IOC component and corresponding version.
        :rtype: Dict
        """
        versions_terminal_list = {}
        for terminal_msg in terminal_msgs:
            msg_version = re.search(VERSION_TERMINAL_PATTERN, terminal_msg.strip())
            msg_component = re.search(COMPONENT_TERMINAL_PATTERN, terminal_msg.strip())
            if msg_version and msg_component:
                msg_version = msg_version.group()
                msg_component = "APP" if msg_component.group(1) == "APPLICATION" else msg_component.group(1)
                versions_terminal_list[msg_component] = msg_version
        return versions_terminal_list

    def assertion_validation(self, component, versions_dlt, versions_terminal):
        """Assert if component version is found on DLT and on SoC terminal

        :param component: Component of IOC
        :type component: String
        :param versions_dlt: All the versions found on DLT
        :type component: Dictionary
        :param versions_terminal: All the versions found on SoC terminal
        :type component: Dictionary
        """
        assert_true(
            bool(
                versions_dlt.get(component, False)
                and versions_terminal.get(component, False)
                and versions_dlt.get(component, False) == versions_terminal.get(component, False)
            ),
            f"""Versions of {component} not found or matched:
                DLT information: '{versions_dlt}'
                SoC terminal information: '{versions_terminal}'
            """,
        )

    def validate_mcu_versions(self, versions_dlt, versions_terminal):
        """Validate if mcu version of ver_gen.txt match with any component version on DLT and terminal

        :param versions_dlt: All the versions found on DLT
        :type component: Dictionary
        :param versions_terminal: All the versions found on SoC terminal
        :type component: Dictionary
        """

        process = os.popen(f"cat {self.ver_gen_path}")
        return_stdout = process.read()
        process.close()
        mcu_version_regex = re.search(VERSION_TERMINAL_PATTERN, return_stdout.splitlines()[0])
        mcu_version = mcu_version_regex.group(0) if mcu_version_regex else None
        logger.debug(f"MCU version found on ver_gen.txt: '{mcu_version}'")
        assert_true(
            bool(
                any(mcu_version == version for version in versions_dlt.values())
                and any(mcu_version == version for version in versions_terminal.values())
            ),
            f"""Version of ver_gen file not found on DLT or in SoC terminal:
                MCU version: '{mcu_version}'
                DLT information: '{versions_dlt}'
                SoC terminal information: '{versions_terminal}'
            """,
        )

    def execute_ipctest(self, cmd):
        """Execute ipctest command and retrieve the number of packets successfully transferred

        :param cmd: ipctest command to be executed

        :return: Number of packets successfully transferred by SoC
        """

        return_stdout, _, _ = self.test.mtee_target.execute_command("chmod +x /var/data/ipctest")
        return_stdout, _, _ = self.test.mtee_target.execute_command(cmd)
        ipctest_output_list = return_stdout.splitlines()

        num_packets_transferred = 0
        line_packets_pattern = re.compile(r".*Number of packets successfully Transferred: (\d*)")
        for line in ipctest_output_list:
            match = re.search(line_packets_pattern, line)
            if match:
                num_packets_transferred = int(match.group(1))
                logger.debug(f"{num_packets_transferred} packets successfully transferred from SoC.")
                break

        return num_packets_transferred

    def execute_ipc_command_and_capture_traces(self, command):
        """
        Start SOC DLT traces and execute SOC Listen test.
        This function will return SOC console output details and SOC DLT traces.
        """
        with self.test.mtee_target.connectors.ioc_dlt.trace as trace:
            return_stdout, _, _ = self.test.mtee_target.execute_command("chmod +x /var/data/ipctest")
            result = self.test.mtee_target.execute_command(command, timeout=5)
            assert_equal(
                result.returncode,
                0,
                f"Failed on executing command {command}. Command stdout: {result.stdout}",
            )

            lines = result.stdout.split("\n")  # Split the string into lines
            size_of_packets = int(lines[1].split(":")[1].strip())
            packets_transferred = int(lines[2].split(":")[1].strip())
            packets_dropped = int(lines[3].split(":")[1].strip())
            msgs = trace.receive(count=0, timeout=10, raise_on_timeout=False, sleep_duration=0)

        return result, size_of_packets, packets_transferred, packets_dropped, msgs

    def validate_soc_console_output(
        self,
        expected_packet_size,
        expected_packet_count,
        actual_packet_size,
        actual_packet_count,
        packets_dropped,
    ):
        """Verifies if all expected size and packets are sent
        :param expected_packet_size: number of packet size sent from cmd
        :type component: integer
        :param expected_packet_count: number of packet sent from cmd
        :type component: integer
        :param actual_packet_size: number of packet size get from console output
        :type component: integer
        :param actual_packet_count: number of packet get from console output
        :type component: integer
        :param packets_dropped: number of packet drop get from console output
        :type component: integer
        """
        assert_equal(
            actual_packet_size,
            expected_packet_size,
            f"Incorrect size of packets... Expected:{expected_packet_size} Actual:{actual_packet_size}",
        )
        assert_equal(
            actual_packet_count,
            expected_packet_count,
            f"Incorrect number of packets tranferred... Expected{expected_packet_count}: Actual:{actual_packet_count}",
        )
        assert_equal(
            packets_dropped,
            0,
            f"Incorrect number of packets dropped... Expected:0 Actual:{packets_dropped}",
        )

    def flash_and_validate_mcu(self):
        if "idcevo" in self.target_name:
            MCU_FLASH_UPDATE_EXPECTED.append(re.compile(r"IDCevo_SBL_[A|B].bin"))
            MCU_FLASH_UPDATE_EXPECTED.append(re.compile(r"IDCevo_APP_[A|B].bin"))
        elif "cde" in self.target_name or "rse26" in self.target_name:
            MCU_FLASH_UPDATE_EXPECTED.append(re.compile(rf"{self.target_name.upper()}_SBL_[A|B].bin"))
            MCU_FLASH_UPDATE_EXPECTED.append(re.compile(rf"{self.target_name.upper()}_APP_[A|B].bin"))

        try:
            mcu_bins = MCU_BINS if os.path.exists(MCU_BINS) else MCU_BINS_SYS
            with with_uploaded_file(mcu_bins, target_file_name="MCU_Binaries") as mcu_target_file:
                cmd = f"iocUpdateUtility -u {mcu_target_file}"
                result = self.test.mtee_target.execute_command(cmd)
            match = validate_output_using_regex_list(result, MCU_FLASH_UPDATE_EXPECTED)
            assert_true(match, f"Failed to validate MCU flashing update, output recieved on flashing: {result.stdout}")
        except Exception as e:
            logger.error(f"Error occured while update flashing MCU using iocUpdateUtility, error - {e}")
            self.test.mtee_target.reboot()

    def check_revision_in_dict(self):
        """
        This function will fetch the MCU Reboot regex patterns mentioned in list "MCU_PATTERNS_ON_REBOOT"
        as per hw_model and service pack under test.
        """
        if self.hw_model in MCU_PATTERNS_ON_REBOOT and self.service_pack in MCU_PATTERNS_ON_REBOOT[self.hw_model]:
            return MCU_PATTERNS_ON_REBOOT[self.hw_model][self.service_pack]
        return False

    def get_lifecycle_count(self, trace, payload):
        """fetch the values from DLT traces as per payload
        The function will return the lifecycle count based on the DLT traces, and if it fails, it will return none.
        """
        for msg in trace:
            matches = payload.search(msg.payload_decoded)
            if matches:
                lifecycle_number = matches.group(1)
                return lifecycle_number

    def reboot_target_and_validate_mcu_and_soc_logs(self, mcu_payload, soc_payload):
        """This function waits for expected DLT payload messages, reboots the target,
        and simultaneously collects SOC and MCU DLT traces. It also verifies that the necessary payloads
        are present in the trace and gets the payload's LC count.
        :param list mcu_payload: expected mcu payloads
        :param list soc_payload: expected soc payloads
        Function will return MCU and SOC lifecycle count as per DLT traces.
        """
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
            with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
                self.test.mtee_target.reboot(prefer_softreboot=False)
                self.test.mtee_target._recover_ssh(record_failure=False)
                mcu_filtered_trace = mcu_trace.wait_for(
                    {"payload_decoded": mcu_payload},
                    timeout=MCU_PAYLOAD_TIMEOUT,
                    count=0,
                    raise_on_timeout=False,
                )
            soc_filtered_trace = soc_trace.wait_for(
                {"payload_decoded": soc_payload},
                timeout=SOC_PAYLOAD_TIMEOUT,
                count=0,
                raise_on_timeout=False,
            )
        validate_expected_dlt_payloads_in_dlt_trace(mcu_filtered_trace, [{"payload_decoded": mcu_payload}], "IOC Logs")
        validate_expected_dlt_payloads_in_dlt_trace(soc_filtered_trace, [{"payload_decoded": soc_payload}], "SOC Logs")

        mcu_lc_count = self.get_lifecycle_count(mcu_filtered_trace, mcu_payload)
        soc_lc_count = self.get_lifecycle_count(soc_filtered_trace, soc_payload)
        self.test.apinext_target.wait_for_boot_completed_flag(240)
        return mcu_lc_count, soc_lc_count

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9497",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "RTOS_BASIC_INFRASTRUCTURE"),
                    config.get("FEATURES", "RTOS_PERIPHERAL_DIAGNOSIS"),
                ],
            },
        },
    )
    def test_001_temperature_monitoring(self):
        """[SIT_Automated] Temperature Monitoring - Verify temperature for all sensors

        Steps:
            - Open IOC DLT instance
            - Get sensors temperature for:
                Sensor 0 - SENSOR_AMBIENT # B1 samples don't have this sensor
                Sensor 1 - SENSOR_UFS
                Sensor 2 - SENSOR_ETH # Not available (IDCEVODEV-9497)
                Sensor 3 - SENSOR_SOC

            - We expect to find the temperatures from the following messages:
                ECU THM  0 log info non-verbose 1 Temperature sensors values:
                ECU THM  0 log info non-verbose 3 - sensor ( 0 ) has X C degrees (x10)
                ECU THM  0 log info non-verbose 5 - sensor ( 1 ) has X C degrees (x10)
                                        ...

            - Validate we found the sensors data for all sensors
            - Validate values are within range of operation
        """
        valid_sensor_values = {}
        invalid_sensor_values = {}
        processed_sensor_values = 0
        ecu_codename = self.test.mtee_target.options.target
        ecu_variant = self.test.mtee_target.options.target_serial_no[2:6].upper()
        hw_variant = self.test.mtee_target.options.hardware_variant

        # SENSOR_ETH is not applicable for RSE, CDE and EVO (B505). Hence popping the validations
        if hw_variant != "SP21" and (ecu_variant != "B506" or ecu_codename != "idcevo"):
            SENSORS_DATA.pop(2)

        # B1 samples don't have sensor 0 data apart from RSE B1 sample
        if self.test.mtee_target.options.hardware_revision == "B1" and "rse" not in ecu_codename:
            SENSORS_DATA.pop(0)

        # Generate a DLT filter per sensor
        sensor_filters_dict = []

        for sensor in SENSORS_DATA.keys():
            sensor_filters_dict.append({"payload_decoded": re.compile(rf".*sensor.*{sensor}.*")})

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker, filters=[("THM", "")]) as trace:
            try:
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=sensor_filters_dict,
                    drop=True,
                    count=len(SENSORS_DATA),
                    timeout=60,
                    raise_timeout_error=True,
                )

                for msg in dlt_msgs:
                    logger.debug(f"Found sensor message: {msg.payload_decoded}")
                    match = GET_SENSOR_TEMP_PATTERN.search(msg.payload_decoded)
                    if match:
                        logger.debug(f"Match GET_SENSOR_TEMP_PATTERN: {match.group(0)}")
                        sensor = int(match.group(1))
                        temp = int(match.group(2)) / 10

                        # Check value is within range
                        if sensor in SENSORS_DATA and SENSORS_DATA[sensor]["min"] < temp < SENSORS_DATA[sensor]["max"]:
                            valid_sensor_values.update({sensor: temp})
                        else:
                            invalid_sensor_values.update({sensor: f"Value out of range {temp} C"})

                    else:
                        match = NO_SENSOR_DATA_PATTERN.search(msg.payload_decoded)

                        if match:
                            logger.debug(f"Match NO_SENSOR_DATA_PATTERN: {match.group(0)}")
                            # The DLT data includes information for sensors 2 and 4. These sensors do not provide
                            # temperature data and it is expected that they do not have this information.
                            sensor = int(match.group(1))
                            logger.error(f"Sensor {sensor}, no data found, instead {msg.payload_decoded}")
                            invalid_sensor_values.update({sensor: msg.payload_decoded})
                        else:
                            raise ValueError(f"Unable to parse sensor message: {msg.payload_decoded}")
                    processed_sensor_values = len(valid_sensor_values) + len(invalid_sensor_values)

            except TimeoutError:
                logger.debug(
                    "Stat of ioc dlt file: %s", Path(self.test.mtee_target.connectors.ioc_dlt.dlt_file).stat()
                )
                # In case TimeoutError happens, the non-verbose ioc dlt file is copied to record what ioc dlt connector
                # really sees at this moment. (For debugging purpose)
                copy_file_name = Path(self.test.mtee_target.connectors.ioc_dlt.dlt_file).stem + ".failure.dlt"
                ioc_dlt_tmp = Path(self.test.mtee_target.options.result_dir) / copy_file_name
                shutil.copyfile(self.test.mtee_target.connectors.ioc_dlt.dlt_file, ioc_dlt_tmp)
                logger.error(
                    "%s is a copy for %s at failing moment. Please check it out for debugging.",
                    ioc_dlt_tmp,
                    self.test.mtee_target.connectors.ioc_dlt.dlt_file,
                )
                raise

            assert_equal(
                processed_sensor_values,
                len(SENSORS_DATA),
                f"Expected {len(SENSORS_DATA)} values."
                f"Got {processed_sensor_values}: {valid_sensor_values} and {invalid_sensor_values}",
            )

            assert_equal(
                0,
                len(invalid_sensor_values),
                f"Some sensors out of range or no data: {invalid_sensor_values}",
            )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8413",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_MCU_LINUX"),
            },
        },
    )
    def test_002_ipc_channels(self):
        """[SIT_Automated] IPC Channels - Confirmation if channels are all available

        Verify all INC channels available and also each channel statistics.

        Steps:
            - Send command to get the channels exposed through FS3ipc:
                # ls -ll /dev/ipc*

            - Check if 31 channels and ipcdebug file are found:
                e.g. /dev/ipc1, /dev/ipc2, ..., /dev/ipc31, /dev/ipcdebug

            - Send command to get each channel statistics:
                # cat /dev/ipcdebug

            - Check if statistics are found for all 31 channels:
                e.g. CH01, CH02, ..., CH31
        """
        logger.info("Starting test to verify all INC channels available and also each channel statistics.")

        ipc_files_list_raw, _, _ = self.test.mtee_target.execute_command("ls -l /dev/ipc*")
        ipc_files_list = self.remove_non_ascii_characters(ipc_files_list_raw).splitlines()
        list_ipc_patterns_found = self.validate_ipc_channels_output(EXPECTED_IPC_CHANNELS, ipc_files_list)
        list_ipc_patterns_missing = list(set(EXPECTED_IPC_CHANNELS) - set(list_ipc_patterns_found))
        logger.info(f"List of ipc patterns missing: {list_ipc_patterns_missing}")
        assert_equal(
            len(list_ipc_patterns_missing),
            0,
            f"The following ipc files were not found: {list_ipc_patterns_missing}",
        )

        ipcdebug_content_list_raw, _, _ = self.test.mtee_target.execute_command("cat /dev/ipcdebug")
        ipcdebug_content_list = self.remove_non_ascii_characters(ipcdebug_content_list_raw).splitlines()
        ipcdebug_content_found = self.validate_ipc_channels_output(EXPECTED_IPCDEBUG_CONTENT, ipcdebug_content_list)
        ipcdebug_content_missing = list(set(EXPECTED_IPCDEBUG_CONTENT) - set(ipcdebug_content_found))
        logger.info(f"ipcdebug patterns missing: {ipcdebug_content_missing}")
        assert_equal(
            len(ipcdebug_content_missing),
            0,
            f"The following ipcdebug channel were not found: {ipcdebug_content_missing}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="SWE.5, SYS.4",
        priority="1",
        duplicates="IDCEVODEV-8372",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "RTOS_BASIC_INFRASTRUCTURE_OS_MCU"),
                ],
            },
        },
    )
    def test_003_verify_ioc_version(self):
        """
        [SIT_Automated] Reset HU and Verify IOC Version

        **Steps**
            - Reset HU using power-supply to force restart of IOC
            - Search in DLT logs for IOC versions
            - Get IOC version through SoC terminal
            - Validate if any version for PBL, SBL, APP were found
            - Compare if versions parsed from DLT and SoC are the same
            - Validate versions found against file ver_gen.txt from Artifactory.

        **Expected outcome**
            - PBL, SBL and APP versions were found both on DLT and on SoC terminal
            - Versions found on DLT and SOC are the same
            - Versions match the ones in the file ver_gen.txt from artifactory
        """

        with self.test.mtee_target.connectors.ioc_dlt.trace as trace:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            msgs = trace.receive(count=0, timeout=5, raise_on_timeout=False, sleep_duration=0)
            dlt_msgs = []
            for ioc_msg in msgs:
                if any(re.match(ioc_regex, ioc_msg.payload_decoded) for ioc_regex in IOC_DATA_MSGS):
                    dlt_msgs.append(ioc_msg.payload_decoded)
            dlt_msgs = list(set(dlt_msgs))
            logger.info(f"Messages found on DLT : '{dlt_msgs}'")

            versions_dlt = self.get_ioc_versions_from_dlt_msgs(dlt_msgs)
            logger.debug(f"IOC versions found on DLT: '{versions_dlt}'")

            return_stdout, _, _ = self.test.mtee_target.execute_command("iocUpdateUtility -v")
            versions_terminal = self.get_ioc_versions_from_soc_terminal_msgs(return_stdout.splitlines())
            logger.debug(f"IOC versions found through terminal: '{versions_terminal}'")

            self.assertion_validation("PBL", versions_dlt=versions_dlt, versions_terminal=versions_terminal)
            self.assertion_validation("SBL", versions_dlt=versions_dlt, versions_terminal=versions_terminal)
            self.assertion_validation("APP", versions_dlt=versions_dlt, versions_terminal=versions_terminal)

            ver_gen_file_exist = os.path.isfile(self.ver_gen_path)
            logger.debug(f"File ver_gen.txt was found: '{ver_gen_file_exist}'")
            if ver_gen_file_exist:
                self.validate_mcu_versions(versions_dlt=versions_dlt, versions_terminal=versions_terminal)
            else:
                logger.warning("File ver_gen.txt was not found. Validation of MCU/IOC version wasn't completed")
                assert_true(False, "File ver_gen.txt was not found. Validation of MCU/IOC version wasn't completed")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8410",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_MCU_LINUX"),
            },
        },
    )
    def test_004_mcu_ipc_maximum_payload(self):
        """[SIT_Automated] INC Communication MCU - Linux Communication- Maximum Payload
        Verify the maximum possible payload length over MCU-Linux IPC Channel.
        Steps:
            - Send ipc test client command with package size 256.
                # /var/data/ipctest -c /dev/ipc20 -t 1 -s 255 -p 10
            - Verify if all packages are correctly sent from SoC:
            - Verify if all packages are correctly received on MCU
        Expected outcome:
            - All packages are correctly received by MCU
        """
        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        filters_dict = [{"payload_decoded": re.compile(r".*MCU listen test: received")}]
        number_of_packets = 10

        self.test.mtee_target._clean_target = False
        self.test.mtee_target.user_data.remount_as_exec()

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker, filters=[("FS3I", "")]) as trace:
            cmd = "/var/data/ipctest -c /dev/ipc20 -t 1 -s 255 -p {0}".format(number_of_packets)
            number_packets_transferred = self.execute_ipctest(cmd)

            dlt_msgs = trace.wait_for_multi_filters(
                filters=filters_dict,
                drop=True,
                count=0,
                timeout=60,
            )

            number_packets_received = len(dlt_msgs)

            logger.info(
                f"Transferred successfully from SoC {number_packets_transferred} of {number_of_packets} packets."
            )
            logger.info(f"Received successfully on MCU {number_packets_received} of {number_of_packets} packets.")

            assert_true(
                bool(number_packets_transferred == number_packets_received == number_of_packets),
                f"Fail to receive all packages from SoC to MCU.\
                Transferred successfully from SoC {number_packets_transferred} of {number_of_packets} packets \
                and received on MCU {number_packets_received} of {number_of_packets} packets.",
            )

    @metadata(
        testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8630",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "RTOS_BASIC_INFRASTRUCTURE_OS_SFI"),
                    config.get("FEATURES", "POWER_MANAGEMENT_VOLTAGE_CONTROL"),
                ],
            },
        },
    )
    @skip("Test needs update due to kernel hardening: IDCEVODEV-325654")
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    def test_005_check_counter_value_from_sfi(self):
        """[SIT_Automated] Check Counter Value from SFI
        Check the counter value / response from SFI, through command in SoC terminal.
        Steps:
            - Send command to access SFI address in SoC terminal
            # devmem 0xF66FFFF8
            - Send the command again to access SFI address in SoC terminal
            # devmem 0xF66FFFF8
        Expected outcome:
            - Check SFI number response
            - Check if SFI number response increase
        """
        command = "devmem 0xF66FFFF8"
        logger.info("Sending the command to check the counter value to access SFI address")
        result = execute_cmd_and_validate(command)
        counter_value_00 = int(result.stdout, 16)

        logger.info("Sending the command again to check the increased counter value to access SFI address")
        result = execute_cmd_and_validate(command)
        counter_value_01 = int(result.stdout, 16)

        assert counter_value_01 > counter_value_00, (
            f"Failed on validating SPI number response increase as Initial value received is: {counter_value_00} and "
            f"the final value received is: {counter_value_01}"
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8428",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_MCU_LINUX"),
            },
        },
    )
    @nose_parametrize(*PACKETS)
    def test_006_ioc_to_soc_listen_test(self, size, packets):
        """[SIT_Automated] INC Test: SOC Listen Test
        Check the reception of the packets sent from IOC to SOC.
        Note: According to most recent information, 1 extra packet is needed to start the
            transmission, so SOC will receive 1 more packet than the ones sent by IOC.
        Steps:
        - Start SOC DLT traces and execute SOC Listen test.
        - Extract SOC packet details from SOC DLT traces.
        - In SOC DLT traces, make sure that packet count is incremented by 1
        - In SOC Console o/p, make sure that packet related details like size, count, dropped packet appears
        as expected
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.mcu_dlt_logs = []
        command = "/var/data/ipctest -c /dev/ipc20 -t 2 -s" + str(size) + " -p " + str(packets)

        # Start SOC DLT traces and execute SOC Listen test.
        (
            result,
            size_of_packets,
            packets_transferred,
            packets_dropped,
            msgs,
        ) = self.execute_ipc_command_and_capture_traces(command)

        # Extract SOC packet details from SOC DLT traces.
        for msg in msgs:
            matches = SOC_SENT_PACKETS.search(msg.payload_decoded)
            if matches:
                lifecycle_number = matches.group(1)
                self.mcu_dlt_logs.append(lifecycle_number)

        # In SOC DLT traces, make sure that packet count is incremented by 1
        logger.info(f"filtered messages: {self.mcu_dlt_logs}")
        assert_equal(
            int(self.mcu_dlt_logs[-1]),
            int(packets + 1),
            f"Incorrect number of packets sent... Expected{packets + 1}: Actual:{self.mcu_dlt_logs[-1]}",
        )

        # In SOC Console o/p, make sure that packet related details like size, count, dropped packet appears
        # as expected
        self.validate_soc_console_output(
            size,
            packets,
            size_of_packets,
            packets_transferred,
            packets_dropped,
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8438",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_MCU_LINUX"),
            },
        },
    )
    @nose_parametrize(*PACKETS)
    def test_007_soc_to_ioc_listen_test(self, size, packets):
        """[SIT_Automated] INC Test: IOC Listen Test
        Check the reception of the packets sent from IOC to SOC.
        Steps:
        - Start SOC DLT traces and execute SOC Listen test.
        - Extract IOC packet details from SOC DLT traces.
        - In SOC Console o/p, make sure that packet related details like size, count, dropped packet appears
        as expected
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.mcu_dlt_logs = []
        command = "/var/data/ipctest -c /dev/ipc20 -t 1 -s" + str(size) + " -p " + str(packets)

        # Start SOC DLT traces and execute SOC Listen test.
        (
            result,
            size_of_packets,
            packets_transferred,
            packets_dropped,
            msgs,
        ) = self.execute_ipc_command_and_capture_traces(command)

        # Extract SOC packet details from SOC DLT traces.
        for msg in msgs:
            matches = IOC_SENT_PACKETS.search(msg.payload_decoded)
            if matches:
                lifecycle_number = matches.group(1)
                self.mcu_dlt_logs.append(lifecycle_number)

        # In SOC DLT traces, make sure that packet count is incremented by 1
        assert_equal(
            int(self.mcu_dlt_logs[-1]),
            int(packets),
            f"Incorrect number of packets sent... Expected{packets}: Actual:{self.mcu_dlt_logs[-1]}",
        )

        # In SOC Console o/p, make sure that packet related details like size, count, dropped packet appears
        # as expected
        self.validate_soc_console_output(
            size,
            packets,
            size_of_packets,
            packets_transferred,
            packets_dropped,
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates=["IDCEVODEV-12133", "IDCEVODEV-15499"],
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "FIRMWARE_FLASHING_MCU"),
            },
        },
    )
    def test_008_verify_mcu_update(self):
        """[SIT_Automated] Verify MCU Update | Utility tool | A/B switching partition
        Steps:
            1. Get MCU_Binaries.zip from artifactory
            2. Trigger the MCU partition flashing using command "iocUpdateUtility -u MCU_Binaries.zip"
            3. Reboot the target
            4. Trigger the MCU partition flasing again using the command
                "iocUpdateUtility -u MCU_Binaries.zip"
            5. Validate if the flashing successful.

        Expected Result:
            - Flashing should be successful for both A and B partitions.
        """
        self.flash_and_validate_mcu()
        self.test.mtee_target.reboot()
        self.flash_and_validate_mcu()

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10282",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT_VOLTAGE_CONTROL"),
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    def test_009_verify_boot_process_wup_wakeup(self):
        """
        [SIT_Automated] Voltage Control - Boot process after waking up from reset
        Steps:
            1. As per HW version and Service pack, fetch the expected o/p from dict - "MCU_PATTERNS_ON_REBOOT"
            2. Start MCU IOC DLT traces and reboot the device.
            3. Verify root login is successful.
            4. Ensure that all payloads fetched from MCU_PATTERNS_ON_REBOOT at step 1 are present in MCU DLT traces.
            5. Ping target on "160.48.199.99" and make sure it's up
        """
        expected_revision = self.check_revision_in_dict()
        assert_true(
            expected_revision, f"Unsupported HW Version. Target:{self.hw_model}, Service Pack:{self.service_pack}"
        )

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            try:
                self.test.mtee_target._console.wait_for_re(
                    rf".*{self.test.mtee_target.options.target} login.*root",
                    timeout=60,
                )
            except Exception as e:
                logger.debug("Root login was not successful as expected after reboot")
                raise AssertionError(
                    f"Aborting the Test since root login failed. Error Occurred: {e}",
                )
            filter_dlt_messages = trace.wait_for_multi_filters(
                expected_revision,
                count=0,
                drop=True,
                timeout=180,
            )
        self.test.mtee_target._recover_ssh(record_failure=False)

        validate_expected_dlt_payloads_in_dlt_trace(filter_dlt_messages, expected_revision, "IOC Logs")

        ping_cmd = f"ping -c 4 {self.test.mtee_target._ip_address}"

        result = run_command(ping_cmd, shell=True)
        assert_process_returncode(0, result, "Ping to ethernet switch was not successful.")

    @metadata(
        testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8663",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "RTOS_BASIC_INFRASTRUCTURE"),
            },
        },
    )
    def test_010_verify_mcu_wakes_up_by_ethernet_wup_trigger(self):
        """
        [SIT_Automated] verify MCU Wakes Up by Ethernet WUP trigger
        Steps:
            1. Start MCU DLT Traces and run below command on Serial Console
                nsg_control --r 0
            2. Trigger Ethernet Wakeup (ETH_WUP)
        Expected Outcome:
            Ensure MCU wakes-up from sleep and payloads mentioned in "mcu_wakeup_expected_payloads_pattern" list
            is present in IOC DLT Traces
        """
        mcu_wakeup_expected_payloads_pattern = [
            {"payload_decoded": re.compile(r".*Switch to VLPS mode initiated.*")},
            {"payload_decoded": re.compile(r".*INIT: Recognized RCM Software Reset Source.*")},
            {"payload_decoded": re.compile(r".*Recognized Wake Up: Ethernet active.*")},
        ]

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            # Executing NSG_CONTROL command for performing MCU to Sleep
            self.test.mtee_target.execute_console_command("nsg_control --r 0")
            try:
                self.test.mtee_target._console.wait_for_re(r".*reboot.*Power down.*", timeout=60)
            except Exception as e:
                logger.debug(f"MCU didn't went to sleep successfully, Exception Occurred: {e}")
            # Waiting for Proper System Sleep
            time.sleep(10)

            # Trigger Ethernet Wakeup(ETH_WUP)
            self.test.mtee_target.wakeup_from_sleep()
            try:
                self.test.mtee_target._console.wait_for_re(
                    rf".*{self.test.mtee_target.options.target} login.*root",
                    timeout=60,
                )
            except Exception as e:
                logger.debug("Rebooting the Target, since MCU didn't wake-up after sleep")
                reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
                raise AssertionError(
                    f"Aborting the Test since MCU didn't wake-up after sleep. Error Occurred: {e}",
                    "Rebooting the target and waiting for application mode",
                )

            filter_dlt_messages = trace.wait_for_multi_filters(
                mcu_wakeup_expected_payloads_pattern,
                count=0,
                drop=True,
                timeout=180,
            )

        validate_expected_dlt_payloads_in_dlt_trace(
            filter_dlt_messages, mcu_wakeup_expected_payloads_pattern, "IOC Logs"
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8426",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "RTOS_BASIC_INFRASTRUCTURE_OS_MCU"),
            },
        },
    )
    @skip("Test is causing the Job Abortion, hence skipping this test")
    def test_011_mcu_lifecycle_number_check_test(self):
        """[SIT_Automated] Check MCU Lifecycle Number
        Steps:
            1. Start the DLT traces, reboot the target, and use the traces to obtain the lifecycle number.
            2. Validate the lifecycle count should be increased on every reboot.
        Expected Outcome:
            After each reboot, the lifecycle count should increase in both the MCU and the SOC logs.
        """
        # Start the DLT traces, reboot the target, and use the traces to obtain the lifecycle number.
        mcu_lc_count_1, soc_lc_count_1 = self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD, SOC_PAYLOAD)
        mcu_lc_count_2, soc_lc_count_2 = self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD, SOC_PAYLOAD)
        # Validate the lifecycle count should be increased.
        assert_equal(
            (int(mcu_lc_count_1) + 1),
            int(mcu_lc_count_2),
            f"After reboot, MCU LC payload number didn't increase as expected. Expected {(int(mcu_lc_count_1) + 1)} "
            f"Actual value {int(mcu_lc_count_2)}",
        )
        assert_equal(
            (int(soc_lc_count_1) + 1),
            int(soc_lc_count_2),
            f"After reboot, SoC LC payload number didn't increase as expected. Expected {(int(mcu_lc_count_1) + 1)} "
            f"Actual value {int(soc_lc_count_2)}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10159",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT_VOLTAGE_CONTROL"),
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    def test_012_verify_boot_process_wup_wakeup(self):
        """
        [SIT_Automated] Verify boot process after waking up by ETH WUP
        Steps:
            1. Trigger MCU sleep using command "nsg_control --r 0" in the SOC console.
            2. Trigger ETH WUP pulse, and validate the expected MCU logs.
            3. Ping the ethernet switch and validate it.
        Expected output:
            1. MCU should enter deep sleep.
            2. Wakeup logs should be seen in MCU logs once ETH WUP pulse is given.
            3. Ping to ethernet switch should work.
        """
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.test.mtee_target.execute_console_command(MCU_SLEEP_CMD)
            assert_true(
                lf.ecu_to_enter_sleep(timeout=60),
                f"ECU failed to sleep after triggering the MCU sleep command - {MCU_SLEEP_CMD}",
            )
            lf.set_default_vehicle_state()
            lf.wakeup_target(wait_for_serial_reboot=False)
            self.test.mtee_target._recover_ssh(record_failure=False)
            filter_dlt_messages = trace.wait_for_multi_filters(
                MCU_ETH_WUP_PULSE_FILTER,
                count=0,
                drop=True,
                timeout=180,
            )
        validate_expected_dlt_payloads_in_dlt_trace(filter_dlt_messages, MCU_ETH_WUP_PULSE_FILTER, "IOC Logs")

        ping_cmd = f"ping -c 4 {self.test.mtee_target._ip_address}"
        result = run_command(ping_cmd, shell=True)
        assert_true(result.returncode == 0, "Ping to ethernet switch was not successful")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-14546",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SUBSYSTEM_LOGGING_SUPPORT_MCU_LOGS"),
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_013_routing_mcu_logs_to_node0_dlt_infrastructure(self):
        """
        [SIT_Automated] [RTOS] : PENT: Routing MCU logs to Node0 DLT Infrastructure
        Steps:
            1. Check for expected ECUID in DLT Traces
                For RSE26 > "RSEM"
                For CDE > "CDEM"
                For IDCEVO > "IDCM"
        Expected Results:
            For Step 1,
                At least one message should be found with expected ECUID in DLT Traces
        """
        messages = []
        if self.target_name == "rse26":
            ecuid = "RSEM"
        elif self.target_name == "cde":
            ecuid = "CDEM"
        elif self.target_name == "idcevo":
            ecuid = "IDCM"
        else:
            raise AssertionError(f"Invalid Target Type!! > {self.target_name}")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
            messages = soc_trace.wait_for(
                {"ecuid": ecuid},
                timeout=10,
                drop=True,
                raise_on_timeout=False,
            )
        assert_true(messages, f"{ecuid} ecuid not found in DLT Traces")
