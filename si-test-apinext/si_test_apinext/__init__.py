"""SI test tools and helpers for IDC Android and RSE"""
__version__ = "1.00"

from pathlib import Path

# Default variables for appium session
DEFAULT_SYSTEM_PORT = 8200
DEFAULT_PORT_SERVER = 4723
DEFAULT_ADB_PORT = 5037
DEFAULT_MJPEG_SERVER_PORT = 9100

# Real phone tests variables
REAL_PHONE_SYSTEM_PORT = DEFAULT_SYSTEM_PORT + 10

# General Android variables
HOME_PATH = str(Path.home())
ANDROID_HOME_PATH = Path(f"{HOME_PATH}/Android/Sdk")
