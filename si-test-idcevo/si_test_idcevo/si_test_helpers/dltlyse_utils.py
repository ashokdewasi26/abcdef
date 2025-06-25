"""DLTlyse utilities"""

import importlib
import logging
import signal
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

target = None

try:
    from mtee.testing.support.target_share import TargetShare

    # pylint: disable=invalid-name
    share = TargetShare()
    if share and hasattr(share, "target"):
        target = share.target
    else:
        target = None
# For local execution
except ImportError:
    logger.warning("Import error, assuming local execution")


class DltlyseCustomHandler:
    """Handler class to deal with the dltlyse analysis process and with custom plugins"""

    def __init__(
        self,
        plugins: List[str],
        dlt_trace_file: List[str],
        plugins_dir: List[str],
        binary: str = "dltlyse" if not target else target.options.dltlyse_bin,
        verbose: bool = True,
        no_default_dir: bool = True,
        timeout: int = 600,
        work_dir=None,
    ) -> None:
        self.plugins = plugins
        self.plugins_dir = plugins_dir
        self.dlt_trace_file = dlt_trace_file
        self.binary = binary
        self.verbose = verbose
        self.no_default_dir = no_default_dir
        self.timeout = timeout
        self.dltlyse_proc = None
        self.work_dir = work_dir

    def start_dltlyse(self) -> str:
        command = [
            self.binary,
            "-x",
            Path(self.work_dir, "posttest_offline_dlt_results.xml"),
        ]
        if self.verbose:
            command += ["--verbose"]
        if self.no_default_dir:
            command += ["--no-default-dir"]
        for directory in self.plugins_dir:
            command += ["-d", directory]
        for plugin in self.plugins:
            command += ["-p", plugin]
        if self.dlt_trace_file:
            for file in self.dlt_trace_file:
                command += [Path(self.work_dir, file)]
        logger.info("Running dltlyse with command: %s", command)
        # create dltlyse process
        with subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, cwd=self.work_dir) as self.dltlyse_proc:
            # wait for the process to finish
            out, _ = self.dltlyse_proc.communicate(timeout=self.timeout)
            # return output
            return out.decode()

    def stop_dltlyse(self):
        if self.dlt_trace_file and self.dltlyse_proc is not None:
            self.dltlyse_proc.send_signal(signal.SIGKILL)


# Keep undersocre in the beggining to mimic MTEE method tee.tee_runner._collect_dltlyse_plugin_package_dirs
def _collect_dltlyse_plugin_package_dirs(
    plugins_dirs: Optional[Iterable[str]], package_names: Optional[Iterable[str]]
) -> List[str]:
    """This method is duplicated from mtee_core due to support local testing"""
    plugins_dirs = list(plugins_dirs or ())
    if package_names:
        # The new dltlyse plugin repos are python packages. These python packages
        # introduce python modules. The python modules should provide `.plugin_path.get_plugin_dir`
        # function, then the plugin dirs could be collected automatically.
        #
        # e.g. dltlyse_plugins_gen22 - https://cc-github.bmwgroup.net/node0/dltlyse-plugins-gen22/
        # It's a python package. After the package is installed, it provides the `dltlyse_plugins_gen22` module.
        # It provides `dltlyse.plugin_path.get_plugin_dir()` function to get the plugin dir.
        # The output value of the function may be `/usr/lib/python3.10/site-packages/dltlyse_plugins_gen22`
        for package_name in package_names:
            module_name = package_name + ".plugin_path"
            try:
                path_module = importlib.import_module(module_name)
                plugins_dirs.append(str(path_module.get_plugin_dir().resolve()))
            except ModuleNotFoundError as err:
                raise RuntimeError(
                    module_name + " not found, please check the values of --dltlyse-plugin-packages"
                ) from err

    logger.info("dltlyse plugin dirs: %s", plugins_dirs)
    return plugins_dirs
