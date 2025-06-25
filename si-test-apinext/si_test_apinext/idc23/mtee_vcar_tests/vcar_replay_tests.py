# Copyright (C) 2023. BMW Car IT GmbH. All rights reserved.
from datetime import datetime
import shlex
import logging
from nose.plugins.skip import SkipTest
from pathlib import Path
import time
from typing import Any, ClassVar, Optional, Tuple

import sh  # type: ignore

from mtee.testing.support.target_share import TargetShare
from mtee.testing.support.vcar_manager import VcarManagerBase
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import check_process_returncode, retry_on_except, run_command
from mtee_apinext.plugins.android_target import AndroidTarget
from tee.tools.vcar_manager import VcarTracePlayer

logger = logging.getLogger(__name__)

VcarModeType = str
VcarLanguageType = str

MTEETarget = Any
APINextTarget = Any
REPLAY_ITERATION_NUMBER = 2
MAX_EXECUTION_TIME = 54000  # 15 hrs


def init_mtee_apinext_idc23_target(target: Optional[MTEETarget] = None) -> APINextTarget:
    target = target or TargetShare().target

    if "idc" not in target.options.target:
        raise NotImplementedError("Not supported to init non-idc target")

    product_type = str(target.options.target) + "_b2"

    return AndroidTarget.valid_products[product_type](
        adb=sh.adb,
        android_home="/opt/android-sdk",
        atest=None,
        fastboot=sh.fastboot,
        serial_number=None,
        _capture_adb_logcat=False,
    )


def reboot_target(apinext_target: APINextTarget, mtee_target: MTEETarget) -> None:
    mtee_target.reboot(prefer_softreboot=False)
    apinext_target.wait_for_adb_device()
    apinext_target.wait_for_boot_completed_flag(wait_time=90)


@retry_on_except(retry_count=2, backoff_time=2)
def connect_to_internet(apinext_target: APINextTarget, mtee_target: MTEETarget) -> None:
    try:
        logger.info("Checking internet connectivity")
        if apinext_target.check_internet_connectivity():
            logger.info("Target is already connected to internet. Skipping connection setup")
            return

        apinext_target.turn_off_airplane_mode()
        apinext_target.enable_bluetooth()
        apinext_target.get_bluetooth_status()
        apinext_target.bootstrap_wifi()
        apinext_target.toggle_wifi_hotspot()
        reboot_target(apinext_target, mtee_target)
        apinext_target.enable_wifi_service()
        apinext_target.connect_to_wifi()
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception("Connect to wifi failed with exception: ", ex)
        raise ex
    else:
        if not apinext_target.check_internet_connectivity():
            raise RuntimeError("Internet connection was not successful")


def switch_vcar_mode_lang(
    target: MTEETarget,
    apinext_target: APINextTarget,
    vcar_manager: VcarManagerBase,
    mode: VcarModeType = "full-replay-someip_21_idc",
    lang: VcarLanguageType = "ENGLISCH__UK",
) -> Tuple[VcarModeType, VcarLanguageType]:
    # Backup original vcar mode and language
    prev_vcar_mode = vcar_manager.get_mode()
    prev_vcar_language = vcar_manager.execute_remote_method("get_language")

    if prev_vcar_mode != mode:
        # Switch to the specific vcar mode
        logger.info("Switch vcar mode: %s (current: %s)", mode, prev_vcar_mode)
        vcar_manager.switch_mode(mode)

        # Reboot the target to effect vcar mode
        logger.info("Reboot to effect the vcar mode (%s) ...", mode)
        reboot_target(apinext_target, target)
        logger.info("Reboot to effect the vcar mode (%s) ... done", mode)

    # Change the vcar language if necessary
    if lang != vcar_manager.execute_remote_method("get_language"):
        logger.info(
            "Switch vcar language: %s (current: %s)",
            lang,
            vcar_manager.execute_remote_method("get_language"),
        )
        vcar_manager.execute_remote_method("set_language", lang)

    return prev_vcar_mode, prev_vcar_language


class TestVcarReplay:
    VCAR_MODE = "full-replay-someip_21_idc"
    VCAR_LANGUAGE = "ENGLISCH__UK"

    target: ClassVar[MTEETarget] = None
    apinext_target: ClassVar[APINextTarget] = None
    vcar_manager: ClassVar[VcarManagerBase] = None

    ori_vcar_mode: ClassVar[str] = ""
    ori_vcar_language: ClassVar[str] = ""

    trace_log_dir: ClassVar[Path] = Path.cwd() / "results"
    screenshot_dir: ClassVar[Path] = Path.cwd() / "results" / "replay_screenshots"
    screenshot_counter: ClassVar[int] = 1

    @classmethod
    def setup_class(cls) -> None:
        cls.target = TargetShare().target
        cls.apinext_target = init_mtee_apinext_idc23_target(cls.target)
        cls.vcar_manager = TargetShare().vcar_manager

        # Switch vcar mode to replay mode
        cls.ori_vcar_mode, cls.ori_vcar_language = switch_vcar_mode_lang(
            cls.target, cls.apinext_target, cls.vcar_manager, cls.VCAR_MODE, cls.VCAR_LANGUAGE
        )
        if cls.target.has_capability(TE.test_bench.farm):
            logger.info("Connect to internet ...")
            connect_to_internet(cls.apinext_target, cls.target)
            logger.info("Connect to internet ... done")
        # Initial result dirs
        cls.trace_log_dir = (Path(cls.target.options.result_dir) / "test_case_reports" / "vcar_replay_log").absolute()
        cls.screenshot_dir = (Path(cls.target.options.result_dir) / "replay_screenshots").absolute()
        for path in (cls.trace_log_dir, cls.screenshot_dir):
            path.mkdir(exist_ok=True, parents=True)

    @classmethod
    def teardown_class(cls) -> None:
        switch_vcar_mode_lang(
            cls.target, cls.apinext_target, cls.vcar_manager, cls.ori_vcar_mode, cls.ori_vcar_language
        )

    @classmethod
    def _take_screenshot(cls, name: str) -> None:
        filename = f"replay_screenshot_{cls.screenshot_counter:03}_{name}.png"
        logger.debug("Take a replay screenshot: %s", filename)
        cls.apinext_target.take_screenshot(cls.screenshot_dir / filename)
        cls.screenshot_counter += 1

    @classmethod
    def _vcar_replay_trace(
        cls,
        test_case_name: str,
        replay_path: Optional[Path] = None,
    ) -> None:
        """
        param: custom_test_name - Custom test name with iteration number to differentiate the logs created
        param: replay_path - Custom replay trace path to be executed

        - Initialize the vcartraceplayer.
        - Stops the player if It's still running.
        - Start the vcar replay, keeps logging every 60s, capture screenshot every 120 sec.
        - Stops the trace player.
        """
        # Use Path(Path(__file__).parent / "full_replay_idc23_2023-04-21.asc.bz2") if the file is in mtee_vcar_tests
        replay_path = replay_path or Path("/vcar/replay/traces/full-replay-someip_21/muc_01_full-replay-21.asc.bz2")
        logger.info("Replay path: %s", replay_path)
        replay_log_path: Path = cls.trace_log_dir / (test_case_name + ".log")

        # Start to replay the trace
        player = VcarTracePlayer(replay_path, replay_log_path, cls.vcar_manager, cls.target)

        for _ in range(3):
            if not player.is_running():
                break
            else:
                player.stop()
                time.sleep(30)
        else:
            raise RuntimeError("Vcar Trace player did not stop after previous run. Tried 3 times to stop the player")

        cls._take_screenshot(f"{test_case_name}_before_init_replay_starting_position")
        player.init_replay_starting_position(timeout=5)
        time.sleep(5)
        cls._take_screenshot(f"{test_case_name}_init_replay_starting_position")
        player.start()
        cls._take_screenshot(f"{test_case_name}_replay_start")
        elapsed_secs = 0
        while player.is_running():
            time.sleep(60)
            elapsed_secs += 60
            logger.info("Vcar replay test case is running - %s ... %s secs", test_case_name, elapsed_secs)
            time.sleep(60)
            elapsed_secs += 60
            cls._take_screenshot(f"{test_case_name}_replay_running_{elapsed_secs:04}")
            logger.info("Vcar replay test case is running - %s ... %s secs", test_case_name, elapsed_secs)
        player.stop()
        cls._take_screenshot(f"{test_case_name}_replay_stop")

    @classmethod
    def _start_navigation(cls, custom_test_name: str = "") -> None:
        """
        Starts the Navigation app
        """
        cls._take_screenshot(f"{custom_test_name}_before_navigation")
        logger.info("Ready to start navigation")
        cls.apinext_target.execute_command(shlex.split("am start -n com.bmwgroup.idnext.navigation/.map.MainActivity"))
        time.sleep(5)
        logger.info("Done to start navigation")
        cls._take_screenshot(f"{custom_test_name}_active_navigation")

    def _run(self, custom_test_name: str = "unknown_test_case_name") -> None:
        """
        param: custom_test_name - Custom test name with iteration number to differentiate the logs created

        - Logs the worker Disk, RAM and Process usage before each iteration.
        - Starts the vcar trace execution and performs the replay
        """
        logger.info("Start the test case: %s", custom_test_name)

        # Log worker disk space
        result = run_command(["df", "-h"], check=True)
        check_process_returncode(0, result, f"Checking worker disk space failed: {result}")
        logger.info(f"Worker disk status: \n{result}")

        # Log worker RAM Usage
        result = run_command(["free", "-h"], check=True)
        check_process_returncode(0, result, f"Checking worker RAM usage failed: {result}")
        logger.info(f"Worker RAM status: \n{result}")

        # Log worker Top 15 process
        cmd = "ps -eo pid,ppid,cmd,comm,%mem,%cpu --sort=-%mem | head -15"
        result = run_command(cmd, check=True, shell=True)
        check_process_returncode(0, result, f"Checking worker top 15 process failed: {result}")
        logger.info(f"Worker process usage for {custom_test_name}: \n{result}")

        self._take_screenshot(f"{custom_test_name}_initial_test_case")

        self._start_navigation(custom_test_name)
        self._vcar_replay_trace(custom_test_name)

        self._take_screenshot(f"{custom_test_name}_after_test_case")

        logger.info("End the test case: %s", custom_test_name)

    def test_001_vcar_replay(self):
        start_time = datetime.now()
        for iteration in range(REPLAY_ITERATION_NUMBER):
            # Run replay in loop
            current_time = datetime.now()
            if (current_time - start_time).total_seconds() < MAX_EXECUTION_TIME:
                yield self._run, "test_001_vcar_replay_{}".format(iteration)
            else:
                msg = f"Maximum execution time exceeded {MAX_EXECUTION_TIME} Seconds. Skipping iteration {iteration}"
                logger.info(msg)
                raise SkipTest(msg)
