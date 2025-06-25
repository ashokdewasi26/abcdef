# Copyright (C) 2022. BMW Car IT. All rights reserved.
import re


class KpiMarker:
    """Class to hold all dlt markers wrt the KPI tests of IDC"""

    APPIUM_CLICK_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"appium\[\d+\]: Click command"),
    }
    USB_SOURCE_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"ActiveSourceInfo.*Playing.*usb"),
    }
    HOME_SCREEN_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"HomeBroadcastReceiver.*com.bmwgroup.idnext.*launcher.LAUNCHER_SHOW"),
    }
    KEYINPUT_MEDIA_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"BMWInputService\[\d+\]: New event: CustomKeyEvent \{ inputCode = START_MEDIA\(1008\),"
            r" action = ACTION_UP\(1\).*\}"
        ),
    }
    KEYINPUT_CONNECTIVITY_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"BMWInputService\[\d+\]: New event: CustomKeyEvent \{ inputCode = START_CONNECTIVITY\(1006\),"
            r" action = ACTION_UP\(1\).*\}"
        ),
    }
    KEYINPUT_MAP_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"BMWInputService\[\d+\]: New event: CustomKeyEvent \{ inputCode = START_MAP\(1010\),"
            r" action = ACTION_UP\(1\).*\}"
        ),
    }
    KEYINPUT_BACK_DLT_PATTERN = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"BMWInputService\[\d+\]: New event: CustomKeyEvent \{ inputCode = DET_ZBE_BACK\(1056\),"
            r" action = ACTION_UP\(1\).*\}"
        ),
    }
    RECEIVED_VEHICLE_PRUEFEN = {
        "apid": "NSM",
        "ctid": "NSM",
        "payload_decoded": re.compile(r"Changed NodeState - NsmNodeState_Shutdown \d+ =.*NsmNodeState_Resume \d+"),
    }
    START_MEDIA_DET = {
        "apid": "ALD",
        "ctid": "SYST",
        "payload_decoded": re.compile(
            r"ActivityTaskManager\[\d+\]: START .* \{act=com.bmwgroup.apinext.mediaapp.action.SHOW flg=.*\}"
        ),
    }
    START_CONNECTIVITY_DET = {
        "apid": "ALD",
        "ctid": "SYST",
        "payload_decoded": re.compile(
            r"ActivityTaskManager\[\d+\]: START .* \{act=com.bmwgroup.idnext.connectivity.action.BMW_ZBE_COM flg=.*\}"
        ),
    }
    START_MAP = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"\[NAVI\]\[MapStyleLifecycleOwner\(main\)\]\[\d+\]: "
            r"map view lifecycle started, starting map style lifecycle."
        ),
    }
    TAP_COMMAND = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"appium\[\d+\]:.*Synthesized: MotionEvent \{ action=ACTION_DOWN.*toolType\[\d+\]=TOOL_TYPE_FINGER.*\}"
        ),
    }
    START_MEDIA_WIDGET = {
        "apid": "ALD",
        "ctid": "SYST",
        "payload_decoded": re.compile(
            r"ActivityTaskManager\[\d+\]: START .* \{act=com.bmwgroup.apinext.mediaapp.action.MEDIA_WIDGET flg=.*\}"
        ),
    }
    START_CONNECTIVITY_WIDGET = {
        "apid": "ALD",
        "ctid": "SYST",
        "payload_decoded": re.compile(
            r"ActivityTaskManager\[\d+\]: START .* \{flg=.* "
            r"cmp=com.bmwgroup.idnext.connectivity/.nav.wizard.NavWizardHostActivity.*\}"
        ),
    }
    SWITCH_USER_START = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"\#PERSO \#SVC \#IN \#PersoSystemServiceImpl\[\d+\]: switchUser.*"),
    }
    SWITCH_USER_END = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"\#DEB \#PERSO \#SVC \#UserBroadcastReceiverImpl\[\d+\]: handleUserPresent\(\).*isGuestUser=true"
        ),
    }
    RESUME_MEDIA = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"mediaapp \(.*\) - MediaActivity\[\d+\]: onResume"),
    }
    NEW_USB_SOURCE_DLT_PATTERN = {
        "apid": "SYS",
        "ctid": "JOUR",
        "payload_decoded": re.compile(r"New USB device found"),
    }
    ROUTE_CALCULATION_START = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(
            r"\[NAVI\]\[ROUTE\]\[RouteSelectionRouteCalculator\]\[\d+\]: "
            r"(Calculate route|Routes are available for CustomerStop).*"
        ),
    }
    ROUTE_CALCULATION_END = {
        "apid": "ALD",
        "ctid": "LCAT",
        "payload_decoded": re.compile(r"\[NAVI\]\[GUID\]\[Guidance\]\[\d+\]: Start guidance called with route id.*"),
    }
