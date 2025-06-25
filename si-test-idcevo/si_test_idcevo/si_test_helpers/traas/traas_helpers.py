import logging
import socket
import subprocess

logger = logging.getLogger(__name__)


class TRAASHelper:
    def __init__(self):
        self.idcevo_ip_addr = self._get_idcevo_addr()
        self.idcevo_diag_addr = "0x63"
        self.icon_ip_addr = self._get_icon_addr()
        self.icon_diag_addr = "0x61"
        self.ipnext_ip_addr = "169.254.146.15"
        self.ipnext_diag_addr = "0x10"
        self.ipbasis_ip_addr = "169.254.154.226"
        self.ipbasis_diag_addr = "0x40"

        self.all_ecu_addr = {
            "idcevo": [self.idcevo_ip_addr, self.idcevo_diag_addr],
            "icon": [self.icon_ip_addr, self.icon_diag_addr],
            "ipnext": [self.ipnext_ip_addr, self.ipnext_diag_addr],
            "ipbasis": [self.ipbasis_ip_addr, self.ipbasis_diag_addr],
        }

        self.idcevo_key = "/ws/files/hu/id_rsa_elk"
        self.icon_key = "/ws/GL_CACHE/id_ed25519_icon-bam"

        self.senddoip_path = "/ws/repos/traas/executors/doip/senddoip.py"

    def _get_idcevo_addr(self):
        """Get IDCEVO address"""
        try:
            ip_addr = socket.gethostbyname("ecu-hu")
        except Exception as err:
            logger.info(f"Failed to get IP of IDCEVO: {err}. Using default IP address")
            ip_addr = "169.254.166.99"
        return ip_addr

    def _get_icon_addr(self):
        """Get ICON address"""
        try:
            ip_addr = socket.gethostbyname("ecu-icon")
        except Exception as err:
            logger.info(f"Failed to get IP of ICON: {err}. Using default IP address")
            ip_addr = "169.254.0.97"
        return ip_addr

    def execute_command_worker(self, command):
        """Execute any command on the worker(NUC)"""
        logger.info("Executing command: %s", command)
        output = subprocess.run(command, shell=True, capture_output=True, check=False)
        logger.info(f"Result: {output.stdout.decode('utf-8')}")
        return output

    def execute_command_idcevo(self, command):
        """Execute command on IDCEVO"""
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            self.idcevo_key,
            f"root@{self.idcevo_ip_addr}",
            command,
        ]
        logger.info("Running on IDCEVO: %s", cmd)
        output = subprocess.run(cmd, check=False, capture_output=True)
        if output.returncode != 0:
            logger.info("Failed to run on IDCEVO: %s", cmd)
            logger.info(f"Command error: {output.stderr}")
        return output

    def execute_command_icon(self, command):
        """Execute command on ICON"""
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            self.icon_key,
            f"root@{self.icon_ip_addr}",
            command,
        ]
        logger.info("Running on ICON: %s", cmd)
        output = subprocess.run(cmd, check=False, capture_output=True)
        if output.returncode != 0:
            logger.info("Failed to run on ICON: %s", cmd)
            logger.info(f"Command error: {output.stderr}")
        return output

    def trigger_diag_job(self, target, diag_hex):
        """Trigger diag job"""
        cmd = f"python3 {self.senddoip_path}"
        ecu_addr = self.all_ecu_addr.get(target.lower(), None)
        if ecu_addr is None:
            logger.info(f"Invalid target: {target}")
            return
        ip_addr, diag_addr = ecu_addr
        cmd += f" --ip-addr {ip_addr} --diag-addr {diag_addr} {diag_hex}"
        return self.execute_command_worker(cmd)
