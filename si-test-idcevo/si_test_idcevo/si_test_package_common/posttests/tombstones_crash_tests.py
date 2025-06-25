import glob
import json
import logging
import os
import pathlib
import sh
import shutil  # noqa: AZ100
import socket
import time

from mtee.testing.support.target_share import TargetShare as MTEEtarget
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import metadata
from mtee_apinext.plugins.android_target import AndroidTarget
from mtee_apinext.targets import TargetShare
from nose.plugins.skip import SkipTest

MTEE_TARGET_MANAGER_IP = "localhost"
MTEE_TARGET_MANAGER_PORT = 5005
logger = logging.getLogger("mtee_apinext.builtin_tests.test_stability")  # pylint: disable=invalid-name


THIS_DIR = pathlib.Path(__file__).parent.resolve()
DEFAULT_WHITELISTED_CRASHES = os.path.join(THIS_DIR, "crash_whitelist")
DEFAULT_WHITELISTED_PROCESS = os.path.join(THIS_DIR, "crash_process_whitelist")


@metadata(testsuite=["BAT", "PDX-endurance", "PDX-stress", "SI-performance", "SI-android", "SI", "IDCEVO-SP21"])
class StabilityPostTest(object):
    __test__ = True

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.sendto(b"SHUTDOWN", (MTEE_TARGET_MANAGER_IP, MTEE_TARGET_MANAGER_PORT))
            time.sleep(30)
    except socket.error as error:
        logger.error("Error while shutting down MTEE target manager: {}".format(error))

    _whitelisted_crashids = []
    # Some crashes are generating tombstones. The tombstone
    # appears in the crash directory and in the tombstone directory.
    # If a crash is white-listed, the associated tombstone from the
    # tombstones directory should also be ignored.
    _whitelisted_tombstones = []
    # some process create crashes due to flakiness of the test which cannot
    # be avoided. Whitelisted processes is a list of those processes
    _whitelisted_processes = []
    # ANRs that can't be hashed, for any reason will be ignored
    _ignore_unhashable_anrs = True
    # Tombstones that can't be hashed, for any reason will be ignored
    _ignore_unhashable_tombstones = True
    # Crashes that can't be hashed, for any reason will be ignored
    _ignore_unhashable_crashes = True
    # Define empty dict to save ANR, CRASH & TOMBSTONE data
    android_crash_metadata = {"Crashes": {}, "Tombstones": {}, "ANRs": {}}
    android_crash_metadata_file = "android_crash_metadata.json"
    not_whitelisted_anrs = []
    not_whitelisted_tombstones = []
    not_whitelisted_crashes = []
    whitelisted_anrs_ids = []
    whitelisted_tombstones_ids = []
    whitelisted_crashes_ids = []

    @classmethod
    def setup_class(cls):
        cls.target = TargetShare().target
        cls.mtee_target = MTEEtarget().target
        cls.dropbox_dir = "/data/system/dropbox"
        cls.tombstones_dir = "/data/tombstones"
        cls.anr_dir = "/data/anr"
        cls.log_dir = "/data/logs"
        cls.crash_log_dir = os.path.join(cls.log_dir, "crash*")
        cls.host_crash_artifacts_dir = "crash_artifacts"
        cls.host_crash_log_dir = os.path.join(cls.host_crash_artifacts_dir, "crashes")
        cls.host_dropbox_dir = os.path.join(cls.host_crash_artifacts_dir, "dropbox")
        cls.host_anr_dir = os.path.join(cls.host_crash_artifacts_dir, "anr")
        cls.dropbox_crash_metadata = {
            "java_crash": "EVENT=CRASH\nTYPE=JAVACRASH",
            "native_crash": "EVENT=CRASH\nTYPE=JAVA_TOMBSTONE",
        }
        cls.dtlyse_coredumps_dir = os.path.join(cls.mtee_target.options.result_dir, "Coredumps")
        logger.info(f"Coredumps dir: '{cls.dtlyse_coredumps_dir}'")

        if cls.mtee_target.has_capability(TE.test_bench.rack):
            _crash_parser_script = "/ws/repos/test-automation/scripts/lib/apinext-crash-parser.py"
        else:
            _crash_parser_script = os.path.abspath(os.path.join(THIS_DIR, "apinext-crash-parser.py"))

        cls.crash_parser = sh.Command(_crash_parser_script).bake("--crash-id")

        os.makedirs(cls.host_crash_artifacts_dir, exist_ok=True)
        # Prioritize ENV variable otherwise search for default file
        whitelisted_crashes = os.environ.get("WHITELISTED_CRASHES")
        if not whitelisted_crashes and os.path.isfile(DEFAULT_WHITELISTED_CRASHES):
            whitelisted_crashes = DEFAULT_WHITELISTED_CRASHES

        if whitelisted_crashes:
            logger.debug("Will read whitelisted crashes from the file %s", whitelisted_crashes)
            with open(whitelisted_crashes, "r") as _wcf:
                for line in _wcf:
                    # sanitize the input a bit
                    crash_line = str(line).strip()
                    # lines starting with # are comments
                    if not crash_line.startswith("#"):
                        cls._whitelisted_crashids.append(crash_line)
        logger.debug("Found the following whitelisted crashes: %s", cls._whitelisted_crashids)

        whitelisted_processes = os.environ.get("WHITELISTED_PROCESS")
        if not whitelisted_processes and os.path.isfile(DEFAULT_WHITELISTED_PROCESS):
            whitelisted_processes = DEFAULT_WHITELISTED_PROCESS
        if whitelisted_processes:
            logger.debug("Will read whitelisted processes from the file %s", whitelisted_processes)
            with open(whitelisted_processes, "r") as _wcp:
                for line in _wcp:
                    crash_process_line = str(line).strip()
                    if not crash_process_line.startswith("#"):
                        cls._whitelisted_processes.append(crash_process_line)
        logger.debug("Found the following whitelisted processes: %s", cls._whitelisted_processes)

        if not cls.target:
            logger.debug("No target instance was returned from mtee-apinext")
            logger.debug("Setting up apinext target")
            target_plugin = AndroidTarget()
            target_class = target_plugin.valid_products["idcevo"]
            TargetShare().target = target_class(
                adb=sh.adb,
                android_home="/opt/android-sdk",
                atest=None,
                fastboot=sh.fastboot,
                serial_number=None,
                _capture_adb_logcat=False,
            )
            cls.target = TargetShare().target

        if cls.target.build_has_root_available:
            cls.user_build = False
        else:
            cls.user_build = True

    @classmethod
    def teardown_class(cls):
        logger.debug("Dump crash data to json file")
        # Remove whitelisted anrs
        for anr in cls.whitelisted_anrs_ids:
            if anr in cls.android_crash_metadata["ANRs"]:
                del cls.android_crash_metadata["ANRs"][anr]
        # Remove whitelisted tombstones
        for tombstone in cls.whitelisted_tombstones_ids:
            if tombstone in cls.android_crash_metadata["Tombstones"]:
                del cls.android_crash_metadata["Tombstones"][tombstone]
        # Remove whitelisted crashes
        for crash in cls.whitelisted_crashes_ids:
            if crash in cls.android_crash_metadata["Crashes"]:
                del cls.android_crash_metadata["Crashes"][crash]
        # Dump data to json file
        with open(os.path.join(cls.host_crash_artifacts_dir, cls.android_crash_metadata_file), "w") as crash_json:
            json.dump(cls.android_crash_metadata, crash_json, indent=4)

    def _check_target_dir(self, target_dir):
        non_empty_dir_found = False
        try:
            output = self._list_target_directory(target_dir, with_root=self.target.file_transfer_requires_root)
            stdout = str(output.stdout, "utf-8").strip()
            if not stdout:
                logger.debug("%s directory exists on target but it is empty.", target_dir)
            else:
                non_empty_dir_found = True
        except sh.ErrorReturnCode_2:
            logger.debug("%s directory does not exist on target.", target_dir)
        except sh.ErrorReturnCode_1 as err:
            logger.debug("Checking target dir %s resulted in error:\n%s", target_dir, err)
            if "Permission denied" in err.stderr.decode("utf-8") or "Permission denied" in err.stdout.decode("utf-8"):
                logger.info("Detected a permission denied error, trying with upgraded privileges")
                output = self._list_target_directory(target_dir, with_root=True)
                stdout = str(output.stdout, "utf-8").strip()
                if not stdout:
                    logger.debug("%s directory exists on target but it is empty.", target_dir)
                else:
                    non_empty_dir_found = True
            else:
                logger.debug(
                    "No Permission Denied text found in the stdout/stderr, error is not correctable, raising:\n%s", err
                )
                raise err
        return non_empty_dir_found

    def _list_target_directory(self, target_dir, with_root=False):
        cmd_prefix = "su 0 " if with_root else ""
        dir_check_cmd = "{}ls -A {}".format(cmd_prefix, target_dir)
        return self.target.execute_command(dir_check_cmd)

    def _pull_from_target(self, source, destination):
        """Pulls a path from the target, autocorrecting permission errors

        :param source: The path on the target that is to be pulled
        :param destination: Where on the test host to pull
        """
        try:
            return self.target.pull(source, destination)
        except sh.ErrorReturnCode_1 as err:
            # For the sake of reading clarity, keeping the x or y syntax instead
            # of concatenating stderr and stdout
            if "Permission denied" in err.stderr.decode("utf-8") or "Permission denied" in err.stdout.decode("utf-8"):
                logger.info("Detected a permission denied error, trying with upgraded privileges")
                try:
                    return self.target.pull_as_root(self.anr_dir, self.host_crash_artifacts_dir)
                except Exception as e:
                    logger.exception(f"Target pull failed with exception: '{e}' \nand error: '{err}'")
                    logger.exception("Target pull as root failed with exception:")
                    raise
            logger.debug(
                "No Permission Denied text found in the stdout/stderr, error is not correctable, raising:\n%s", err
            )
            raise err

    def _check_crash_logs_node0_product(self):
        if not self.user_build:
            logger.debug("Pulling dropbox data from target to %s", self.host_dropbox_dir)
            self._pull_from_target(self.dropbox_dir, self.host_dropbox_dir)
            crash_logs = glob.glob(os.path.join(self.host_dropbox_dir, "*_crash*"))
        else:
            # target is flashed with a user build. pulling from dropbox dir won't work.
            # We use coredumps extracted from DLT.
            logger.debug("Using crash data from dlt since a user build is flashed")
            crash_logs = glob.glob(os.path.join(self.dtlyse_coredumps_dir, "*_crash*"))
            logger.debug("Crashes detected from dltlyse: %s", crash_logs)
            logger.debug(
                "Coredumps detected from dltlyse [NOT ANALYSED]: %s",
                glob.glob(os.path.join(self.dtlyse_coredumps_dir, "core.*.gz")),
            )

        if not crash_logs:
            crashes_detected = False
        else:
            crashes_detected = True
            crash_counter = 0
            logger.debug("Found following crashes: %s", crash_logs)
            for crash_log in crash_logs:
                logger.debug("Processing crash log: %s", crash_log)
                crash_type = "undefined"
                crashlog_dir = os.path.join("crash_artifacts", "crashes", "crashlog_{}".format(crash_counter))
                os.makedirs(crashlog_dir, exist_ok=True)
                crash_counter += 1
                shutil.copy2(crash_log, crashlog_dir)
                # Generate crash metadata required for whitelisting
                if "system_app_crash" in crash_log:
                    crash_type = "java_crash"
                    logger.debug("Detected Java crash")
                elif "system_server_native_crash" in crash_log:
                    crash_type = "native_crash"
                    logger.debug("Detected native crash")
                else:
                    logger.warning("Crash type could not be determined")
                if crash_type != "undefined":
                    with open(os.path.join(crashlog_dir, "crashfile"), "w") as crash_file:
                        crash_file.write(self.dropbox_crash_metadata[crash_type])
        return crashes_detected

    def _check_crash_logs_legacy(self):
        crashes_detected = False
        crash_logs = []
        list_crash_logs_cmd = "ls -d {}".format(self.crash_log_dir)
        try:
            # the crashes are grouped 1 / directory, each with an unique ID
            result = self.target.execute_command(list_crash_logs_cmd)
            crash_logs = str(result.stdout, "utf-8").splitlines()
        except sh.ErrorReturnCode_1 as err:
            logger.debug(err)
            logger.debug("Crash logs not found on target.")
        if crash_logs:
            logger.debug("Found the following crashes: %s", crash_logs)
            crashes_detected = True
            for crash_log_dir in crash_logs:
                logger.debug("Detected crash %s, pulling to %s", crash_log_dir, self.host_crash_log_dir)
                self.target.pull(crash_log_dir, self.host_crash_log_dir, timeout=30)
        return crashes_detected

    def _check_crash_logs(self):
        crashes_detected = self._check_crash_logs_node0_product()
        return crashes_detected

    def test_anr(self):
        if self.user_build and self.target.product_type == "bmw_rse22_ext":
            raise SkipTest("Skipping ANR check as root access is not possible and target is Extension board")
        if not self.user_build:
            anr_found = self._check_target_dir(self.anr_dir)
        else:
            logger.debug("User build flashed on target. Getting ANRs from dltlyse")
            anr_found = glob.glob(os.path.join(self.dtlyse_coredumps_dir, "*_anr*"))
            logger.debug("Found the following ANRs from dltlyse: %s", anr_found)

        # Check traces for 'application not responding' i.e. application freeze conditions
        if anr_found:
            if not self.user_build:
                self._pull_from_target(self.anr_dir, self.host_crash_artifacts_dir)
                anr_list = glob.glob(os.path.join(self.host_anr_dir, "anr_*"))
            else:
                anr_list = anr_found
            for anr_file in anr_list:
                crash_parser_output = self._create_crash_id(
                    crash_path=anr_file,
                    crash_type="ANR",
                    crash_id_file_name=os.path.basename(anr_file) + ".mtee.crashid.txt",
                )
                if crash_parser_output:
                    anr_id, anr_process = crash_parser_output.split(",")
                    occurrence = 1
                    if anr_id in self.android_crash_metadata["ANRs"]:
                        occurrence = self.android_crash_metadata["ANRs"][anr_id][2] + 1
                    self.android_crash_metadata["ANRs"].update({anr_id: [anr_process, anr_file, occurrence]})
                else:
                    anr_id = None
                if anr_id is None:
                    if not self._ignore_unhashable_anrs:
                        logger.debug(
                            "ANR %s is unhashable and ignoring the unhashable ANRs is "
                            "not enabled via environment variable TA_IGNORE_UNHASHABLE_ANRS",
                            anr_file,
                        )
                        self.not_whitelisted_anrs.append(anr_file)
                elif anr_id not in self._whitelisted_crashids:
                    logger.debug("ANR %s with anr_id %s is not white listed", anr_file, anr_id)
                    self.not_whitelisted_anrs.append(anr_file)
                else:
                    logger.debug("ANR %s with hash %s is whitelisted, skipping", anr_file, anr_id)
            # Emulator in CI is quite slow. Skip ANR check - ABPI-137795
            if "emulator" in self.target.product_type:
                raise SkipTest("Skipping ANR check for emulator")
            else:
                if not self.user_build:
                    assert len(self.not_whitelisted_anrs) == 0, (
                        "ANR logs found: %s. Check test-artifacts/crash_artifacts/anr dir." % self.not_whitelisted_anrs
                    )
                else:
                    assert len(self.not_whitelisted_anrs) == 0, (
                        "ANR logs found: %s. Check test-artifacts/results/extracted_files/Coredumps dir."
                        % self.not_whitelisted_anrs
                    )
        else:
            logger.debug("No ANRs found in this run, congratulations!")

    def test_crash(self):
        # Check Java crash logs which are created for crashes of Java code
        if self.user_build and self.target.product_type == "bmw_rse22_ext":
            raise SkipTest("Skipping crash check as root access is not possible and target is Extension board")
        os.makedirs(self.host_crash_log_dir, exist_ok=True)
        crashes_detected = self._check_crash_logs()
        if not crashes_detected:
            return
        for crash_log_dir in os.listdir(self.host_crash_log_dir):
            log_dir_abs = os.path.abspath(os.path.join(self.host_crash_log_dir, crash_log_dir))
            # if the target is MGUPP it's historic, right  ?
            if self.target.product_type == "mvp_mgupp":
                logger.debug("MGUPP target detected, checking if the crash folders are not empty")
                dir_size = sum(entry.stat().st_size for entry in os.scandir(log_dir_abs) if entry.is_file())
                if dir_size == 0:
                    logger.warning("Empty crash logs found for MGUPP.")
                    logger.debug(
                        "The crash log dir %s was found on the MGUPP target but it's empty. " "Not processing it.",
                        log_dir_abs,
                    )
                    continue
            crash_parser_output = self._create_crash_id(log_dir_abs)
            if crash_parser_output:
                crash_id, crash_process = crash_parser_output.split(",")
                logger.debug("Computed crash id %s for crash %s", crash_id, crash_log_dir)
                occurrence = 1
                if crash_id in self.android_crash_metadata["Crashes"]:
                    occurrence = self.android_crash_metadata["Crashes"][crash_id][2] + 1
                self.android_crash_metadata["Crashes"].update({crash_id: [crash_process, crash_log_dir, occurrence]})
            else:
                crash_id, crash_process = (None, None)
            # HU22DM-15023
            if crash_id is None:
                if self._ignore_unhashable_crashes:
                    logger.warning("Found non-hashable crash dir %s. Ignoring it.", crash_log_dir)
                    continue
                else:
                    logger.warning(
                        "Found non-hashable crash dir %s. But not ignoring according to job config.", crash_log_dir
                    )
            # If crash_id is not white listed,
            # add it to the list of crashes to be reported.
            if crash_id not in self._whitelisted_crashids:
                if crash_process not in self._whitelisted_processes:
                    logger.debug("Crash %s with crash_id %s is not white listed", crash_log_dir, crash_id)
                    self.not_whitelisted_crashes.append(crash_log_dir)
            else:
                logger.debug("Crash %s with crash_id %s is white listed", crash_log_dir, crash_id)
                # Crash is relevant and whitelisted, attempt to whitelist the tombstones
                tombstones = glob.glob(os.path.join(log_dir_abs, "tombstone_??"))
                if tombstones:
                    logger.debug(
                        "Whitelisting tombstone %s as it is part of crash %s (Crash ID %s)",
                        os.path.basename(tombstones[0]),
                        crash_log_dir,
                        crash_id,
                    )
                    self._whitelisted_tombstones.append(os.path.basename(tombstones[0]))
                else:
                    logger.debug("No tombstones found for crash %s (Crash ID %s)", crash_log_dir, crash_id)

        if not self.user_build:
            assert len(self.not_whitelisted_crashes) == 0, (
                "Crash logs found: %s. Check test-artifacts/crash_artifacts/crashes dir for crash logs."
                % self.not_whitelisted_crashes
            )
        else:
            assert len(self.not_whitelisted_crashes) == 0, (
                "Crash logs found: %s. Check test-artifacts/results/extracted_files/Coredumps for crash logs."
                % self.not_whitelisted_crashes
            )
        logger.debug("No crashes found in this run, congratulations!")

    def _create_crash_id(self, crash_path, crash_type=None, crash_id_file_name="mtee.crashid.txt"):
        """Calls the crash parser in order to determine a crash ID

        The determined crash ID is also written to the mtee.crashid.txt
        file within the crash_path.

        :param crash_path: The path on the local system where the crash is located.
        :param crash_type: The crash type. Will be autodected if not specified.
                           Until further notice, use all caps strings.
        :param crash_id_file_name: The file name where to write the crash ID.
                                   Default: mtee.crashid.txt
        :return: The crash ID (hex string,  MD5) and crash process or None in case it can't be determined
        """
        crash_id_dir = crash_path if os.path.isdir(crash_path) else os.path.dirname(crash_path)
        crash_id_file = os.path.join(crash_id_dir, crash_id_file_name)
        try:
            # create the crashID file and store the result in a local variable
            crash_parser_output = (
                self.crash_parser(crash_path, "--crash-type", crash_type)
                if crash_type
                else self.crash_parser(crash_path)
            )
            output = str(crash_parser_output.stdout, "utf-8")
            logger.debug("Computed crash_parser_output: %s", output)
            crash_id = str(crash_parser_output.stdout, "utf-8").split(",")[0]
            logger.debug("Computed crash_id found: %s ", crash_id)
            with open(crash_id_file, mode="w") as _crash_id_file:
                _crash_id_file.write(crash_id)
            # crash_id is initially a completed command item, let's convert it to a string
            # the stdout property of the completed command object
            return str(crash_parser_output.stdout, "utf-8")
        except sh.ErrorReturnCode as crash_id_err:
            logger.warning("Could not compute crash id from %s", crash_path)
            logger.debug("Creating the crash ID failed with: %s", crash_id_err)
            logger.debug("Stderr: %s", crash_id_err.stderr)

            return None

    def test_tombstones(self):
        if self.user_build and self.target.product_type == "bmw_rse22_ext":
            raise SkipTest("Skipping Tombstones check as root access is not possible and target is Extension board")
        # some tombstones might be whitelisted directly, using the same mechanism as the crashes
        directly_whitelisted_tombstones = set()
        if not self.user_build:
            # Check tombstones which are created for native crashes
            tombstones_found = self._check_target_dir(self.tombstones_dir)
            if tombstones_found:
                self._pull_from_target(self.tombstones_dir, self.host_crash_artifacts_dir)
                # In Android S, every tombstone file is accompanied by a .pb file
                # This is a protobuf file containing info about tombstone in binary format
                # Ignore this file for deciding test status and crash id calculation
                all_tombstones = [
                    tombstone_file
                    for tombstone_file in os.listdir(os.path.join(self.host_crash_artifacts_dir, "tombstones"))
                    if not tombstone_file.endswith(".pb")
                ]
        else:
            logger.debug("User build flashed on target. Getting tombstones data from dltlyse")
            # In Android S, every tombstone file is accompanied by a .pb file
            # This is a protobuf file containing info about tombstone in binary format
            # Ignore this file for deciding test status and crash id calculation
            tombstones_found = glob.glob(os.path.join(self.dtlyse_coredumps_dir, "tombstone_*[!pb]"))
            logger.debug("Found the following tombstones from dltlyse: %s", tombstones_found)
            all_tombstones = tombstones_found
        if tombstones_found:
            # pulling the tombstones is just the 1st part.
            # some of the tombstones are part of the crashes that could
            # have been whitelisted. Let's walk through the tombstones and
            # let's evaluate if they are part of the whitelisted crashes
            self.not_whitelisted_tombstones = set(
                tombstone for tombstone in all_tombstones if tombstone not in self._whitelisted_tombstones
            )

            # try to hash and check the crash whitelist for some of the tombstone hashes
            for tombstone in self.not_whitelisted_tombstones:
                crash_id_filename = os.path.basename(tombstone) + ".mtee.crashid.txt"
                crash_parser_output = self._create_crash_id(
                    crash_path=os.path.abspath(os.path.join(self.host_crash_artifacts_dir, "tombstones", tombstone)),
                    crash_type="TOMBSTONE",
                    crash_id_file_name=crash_id_filename,
                )
                if crash_parser_output:
                    tombstone_crash_id, _ = crash_parser_output.split(",")
                    occurrence = 1
                    if tombstone_crash_id in self.android_crash_metadata["Tombstones"]:
                        occurrence = self.android_crash_metadata["Tombstones"][tombstone_crash_id][2] + 1
                    self.android_crash_metadata["Tombstones"].update(
                        {tombstone_crash_id: [_, crash_id_filename, occurrence]}
                    )
                else:
                    tombstone_crash_id = None
                if tombstone_crash_id is None:
                    if self._ignore_unhashable_tombstones:
                        logger.info("Tombstone %s is not hashable. Ignoring it", tombstone)
                        directly_whitelisted_tombstones.add(tombstone)
                else:
                    logger.debug("Created ID %s for tombstone %s", tombstone_crash_id, tombstone)
                    if tombstone_crash_id in self._whitelisted_crashids:
                        directly_whitelisted_tombstones.add(tombstone)
                        logger.debug("Found the tombstone to be whitelisted via crash ID")
            # some of the tombstones might be directly whitelisted and not tied to a crash
            self.not_whitelisted_tombstones = self.not_whitelisted_tombstones - directly_whitelisted_tombstones
            if self.not_whitelisted_tombstones:
                logger.debug(
                    "Found the following tombstones that were not part of any whitelist: %s",
                    self.not_whitelisted_tombstones,
                )
                if not self.user_build:
                    assert (
                        len(self.not_whitelisted_tombstones) == 0
                    ), "Tombstones detected. Check test-artifacts/crash_artifacts/tombstones for traces."
                else:
                    raise AssertionError(
                        "Tombstones detected. Check test-artifacts/results/extracted_files/Coredumps for traces."
                    )
