import json
import logging

from collections import defaultdict
from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.support.target_share import TargetShare
from si_test_idcevo.si_test_helpers.str_helpers import MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT

target = TargetShare().target
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()


class GenericReporter:
    """Generic template to add test report"""

    REPORT_DIR = Path(target.options.result_dir) / "reports"
    HUMAN_READABLE_SUMMARY_KEYS = {
        "is_passed": "Test case passed",
        "total_execution_time": "Total execution time",
    }

    def __init__(self, test_name, report_filename=None, description=""):
        """
        Init the reporter

        :param str test_name: for logging
        :param Optional[str] report_filename: the report filename.
            The default value is "{test_name}_robustness_report.json"
        :param Optional[str] description: description of the report test"
        """
        self.test_name = test_name
        self.description = description
        self.report_path = self.REPORT_DIR / (report_filename or f"{self.test_name}_report.json")

        self._report = {
            "test_name": self.test_name,
            "description": self.description,
            "summary": {},
            "boot_cycle_summary": {},
        }

    def _add_boot_cycle_summary(self, cycle_num, boot_summary):
        self._report["boot_cycle_summary"][cycle_num] = boot_summary

    def _generate_summary(self, summary):
        self._report["summary"] = summary

    def _print_summary(self):
        """Print summary to stderr for showing the summary in result.html"""
        summary = {
            self.HUMAN_READABLE_SUMMARY_KEYS[key] if key in self.HUMAN_READABLE_SUMMARY_KEYS else key: value
            for key, value in self._report["summary"].items()
        }

        logger.info(summary)

    def report(self, summary):
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

        self._generate_summary(summary)
        self._print_summary()

        # Write the report with json format
        with self.report_path.open("w") as report_out:
            json.dump(self._report, report_out, indent=4)


class RobustnessLifecycleReporter(GenericReporter):
    def __init__(self, test_name, report_filename=None, description=""):

        self.num_reboot = 0
        self.num_reboot_failed = 0
        self.total_execution_time = 0

        self.REPORT_DIR = Path(target.options.result_dir) / "robustness_switch_modes_tests"
        self.HUMAN_READABLE_SUMMARY_KEYS = {
            "is_passed": "Test case passed",
            "number_of_reboots": "Number of reboots",
            "total_execution_time": "Total execution time",
            "reboot_failed": "Number of reboots failed",
            "app_to_app": "Number of reboots from APP to APP",
            "app_to_bolo": "Number of reboots from APP to BOLO",
            "bolo_to_app": "Number of reboots from BOLO to APP",
            "bolo_to_bolo": "Number of reboots from BOLO to BOLO",
            "unknown_to_app": "Number of reboots from UNKNOWN(previous reboot failed) to APP",
            "unknown_to_bolo": "Number of reboots from UNKNOWN(previous reboot failed) to BOLO",
        }
        super().__init__(test_name, report_filename, description)

    def add_report_summary(self):
        """
        Add summary to the report and calculate the reboot statistics
        """
        reboot_stats = {
            "app_to_app": 0,
            "app_to_bolo": 0,
            "bolo_to_app": 0,
            "bolo_to_bolo": 0,
            "unknown_to_app": 0,
            "unknown_to_bolo": 0,
        }
        for _, value in self._report["boot_cycle_summary"].items():
            previous_boot_mode = value.get("previous_boot_mode", "")
            boot_mode = value.get("boot_mode", "")
            if previous_boot_mode == "APP" and boot_mode == "APP":
                reboot_stats["app_to_app"] += 1
            elif previous_boot_mode == "APP" and boot_mode == "BOL":
                reboot_stats["app_to_bolo"] += 1
            elif previous_boot_mode == "BOL" and boot_mode == "APP":
                reboot_stats["bolo_to_app"] += 1
            elif previous_boot_mode == "BOL" and boot_mode == "BOL":
                reboot_stats["bolo_to_bolo"] += 1
            elif previous_boot_mode == "" and boot_mode == "APP":
                reboot_stats["unknown_to_app"] += 1
            elif previous_boot_mode == "" and boot_mode == "BOL":
                reboot_stats["unknown_to_bolo"] += 1

        self.report(
            summary={
                "is_passed": not self.num_reboot_failed,
                "number_of_reboots": self.num_reboot,
                "total_execution_time": self.total_execution_time,
                "reboot_failed": self.num_reboot_failed,
                **reboot_stats,
            }
        )


class MultipleRebootsKPIsReporter(GenericReporter):
    def __init__(self, test_name, report_filename=None, description=""):

        self.reboots_amount = 0
        self.individual_KPIs_to_collect = 0
        self.values_collected_amount = 0
        self.values_not_collected_amount = 0
        self.missing_kpis = defaultdict(list)

        self.REPORT_DIR = Path(target.options.result_dir) / "multiple_reboots_kpi_tests"
        super().__init__(test_name, report_filename, description)

    def add_report_summary(self):

        self.report(
            summary={
                "reboots_amount": self.reboots_amount,
                "Individual_KPIs_to_collect_amount": self.individual_KPIs_to_collect,
                "values_collected_amount": self.values_collected_amount,
                "values_not_collected_amount": self.values_not_collected_amount,
                "Missing_KPIs_in_these_reboots": self.missing_kpis,
            }
        )


class IterativeSTRReporter(GenericReporter):
    """This class is used to gather STR statistics from '[SIT_Automated] STR Iterative Test'
    and report them in .json format"""

    def __init__(self, test_name, report_filename=None, description="", str_cycles=1):
        self.str_cycles = str_cycles
        self.num_str_pre_check_failed = 0
        self.num_str_post_check_failed = 0
        self.total_time_entering_str = 0
        self.total_time_exiting_str = 0
        self.total_str_time = 0
        self.time_metrics = {
            "average_time_to_enter_str_in_seconds": 0,
            "average_time_to_exit_str_in_seconds": 0,
            "max_time_to_enter_str_in_seconds": 0,
            "max_time_to_exit_str_in_seconds": 0,
            "min_time_to_enter_str_in_seconds": float("inf"),  # Positive infinity
            "min_time_to_exit_str_in_seconds": float("inf"),  # Positive infinity
            "number_of_str_cycles_failed": 0,
            "total_number_of_str_cycles": self.str_cycles,
        }

        self.HUMAN_READABLE_SUMMARY_KEYS = {
            "is_test_success": "Test case passed",
            "total_number_of_str_cycles": "Total number of STR cycles performed during the test",
            "total_time_spent_in_str_state_in_seconds": (
                "Total time elapsed with target in STR state during the test, in seconds",
            ),
            "average_time_to_enter_str_in_seconds": "Average time it took for the ECU to enter STR, in seconds",
            "average_time_to_exit_str_in_seconds": "Average time it took for the ECU to exit STR, in seconds",
            "number_of_str_cycles_failed": "Number of STR cycles failed",
            "number_of_str_post_check_validations_failed": "Number of STR post-check validations failed",
        }

        super().__init__(test_name, report_filename, description)

        self._report.pop("boot_cycle_summary")
        self._report["str_cycle_summary"] = {}

    def add_report_summary(self):
        """
        This method is called after all STR cycles are completed.
        It gathers overall metrics for all STR cycles combined and stores them in the _report variable,
        for further reporting. This are the metrics gathered by this method:
            - average_time_to_enter_str_in_seconds: Average time it took for the ECU to enter STR, in seconds
            - average_time_to_exit_str_in_seconds: Average time it took for the ECU to exit STR, in seconds
            - is_test_success: True if all STR cycles were successful, False otherwise
            - total_number_of_str_cycles: Total number of STR cycles performed during the test
            - total_time_spent_in_str_state_in_seconds: Total time target spent in suspended state during the test
            - number_of_str_cycles_failed: Number of STR cycles failed
            - number_of_str_pre_check_validations_failed: Number of STR pre check validations failed
            - number_of_str_post_check_validations_failed: Number of STR post check validations failed
        """
        # This statement ensures we don't get a division by 0 when all the STR cycles failed
        if not self.time_metrics["number_of_str_cycles_failed"] == self.str_cycles:
            self.time_metrics["average_time_to_enter_str_in_seconds"] = self.total_time_entering_str / (
                self.str_cycles - self.time_metrics["number_of_str_cycles_failed"]
            )
            self.time_metrics["average_time_to_exit_str_in_seconds"] = self.total_time_exiting_str / (
                self.str_cycles - self.time_metrics["number_of_str_cycles_failed"]
            )
        else:
            self.time_metrics["average_time_to_enter_str_in_seconds"] == 0
            self.time_metrics["average_time_to_exit_str_in_seconds"] == 0

        self._report["summary"] = {
            "is_test_success": (
                not self.time_metrics["number_of_str_cycles_failed"]
                and not self.num_str_pre_check_failed
                and not self.num_str_post_check_failed
            ),
            "total_number_of_str_cycles": self.str_cycles,
            "total_time_spent_in_str_state_in_seconds": self.total_str_time,
            "average_time_to_enter_str_in_seconds": self.time_metrics["average_time_to_enter_str_in_seconds"],
            "average_time_to_exit_str_in_seconds": self.time_metrics["average_time_to_exit_str_in_seconds"],
            "number_of_str_cycles_failed": self.time_metrics["number_of_str_cycles_failed"],
            "number_of_str_pre_check_validations_failed": self.num_str_pre_check_failed,
            "number_of_str_post_check_validations_failed": self.num_str_post_check_failed,
        }
        # This call generates the .json file with all content present in _report variable
        self.report(self._report["summary"])

        # This loop ensures that all metrics present in 'time_metrics' are published in InfluxDB
        for metric, value in self.time_metrics.items():
            metric_logger.publish(
                {
                    "name": self.test_name,
                    "metric": metric,
                    "value": value,
                }
            )

    def add_str_cycle_summary(
        self,
        str_cycle,
        str_success,
        str_pre_check_success,
        str_post_check_success,
        error_msg,
        str_time,
        time_to_enter_str,
        time_to_exit_str,
        expect_cold_boot,
    ):
        """
        This method is called after each single STR cycle and gathers cycle's statistics and metrics,
        which are stored in _report variable, for further reporting.
        These are the statistics gathered in this method:
            - is_str_success: True if the STR cycle was successful, False otherwise
            - is_str_pre_check_success: True if the STR pre check verifications were successful, False otherwise
            - is_str_post_check_success: True if the STR post check verifications were successful, False otherwise
            - error_message: Information on the error detected during, before, or after the STR cycle
            - str_cycle_duration_in_seconds: Time spent by the target in suspended state
            - time_it_took_to_enter_str_in_seconds: Time it took for the target to suspend after switching to PARKEN
            - time_it_took_to_exit_str_in_seconds: Time it took for the target to resume after switching to WOHNEN
        """

        # This handles the case when a cold boot was expected during the STR cycle
        if expect_cold_boot:
            self._report["str_cycle_summary"][str_cycle] = {
                "is_cold_boot_success": str_success,
                "message": (
                    f"As this was the {MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT}th consecutive iteration, "
                    "a cold boot was expected! Resume Number should be 0"
                ),
                "error_message": error_msg,
            }
            if not str_success:
                self.time_metrics["number_of_str_cycles_failed"] += 1

        # When all steps and verifications of the STR cycle were successful
        elif str_pre_check_success and str_success and str_post_check_success:
            self._report["str_cycle_summary"][str_cycle] = {
                "is_str_success": str_success,
                "is_str_pre_check_success": str_pre_check_success,
                "is_str_post_check_success": str_post_check_success,
                "error_message": error_msg,
                "str_cycle_duration_in_seconds": str_time,
                "time_it_took_to_enter_str_in_seconds": time_to_enter_str,
                "time_it_took_to_exit_str_in_seconds": time_to_exit_str,
            }
            self.total_time_entering_str += time_to_enter_str
            self.total_time_exiting_str += time_to_exit_str
            self.total_str_time += str_time

            if time_to_enter_str > self.time_metrics["max_time_to_enter_str_in_seconds"]:
                self.time_metrics["max_time_to_enter_str_in_seconds"] = time_to_enter_str
            if time_to_enter_str < self.time_metrics["min_time_to_enter_str_in_seconds"]:
                self.time_metrics["min_time_to_enter_str_in_seconds"] = time_to_enter_str
            if time_to_exit_str > self.time_metrics["max_time_to_exit_str_in_seconds"]:
                self.time_metrics["max_time_to_exit_str_in_seconds"] = time_to_exit_str
            if time_to_exit_str < self.time_metrics["min_time_to_exit_str_in_seconds"]:
                self.time_metrics["min_time_to_exit_str_in_seconds"] = time_to_exit_str

        # When the iteration failed during the pre check verifications
        elif not str_pre_check_success:
            self._report["str_cycle_summary"][str_cycle] = {
                "is_str_success": str_success,
                "is_str_pre_check_success": str_pre_check_success,
                "is_str_post_check_success": str_post_check_success,
                "error_message": error_msg,
            }
            self.num_str_pre_check_failed += 1

        # When the iteration failed during the STR routine or during post check verifications
        else:
            self._report["str_cycle_summary"][str_cycle] = {
                "is_str_success": str_success,
                "is_str_pre_check_success": str_pre_check_success,
                "is_str_post_check_success": str_post_check_success,
                "error_message": error_msg,
            }
            # If the failure was during the STR routine
            if not str_success:
                self.time_metrics["number_of_str_cycles_failed"] += 1
            # If the failure was during post check verifications
            else:
                self.num_str_post_check_failed += 1
