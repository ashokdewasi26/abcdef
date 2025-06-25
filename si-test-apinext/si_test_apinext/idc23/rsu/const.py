# Payloads for RSU process verification
# Each tuple contains Step name, Payload to look for, timeout, OBD status after payload found, Trigger PAD, wait time
RSU_PAYLOADS = (
    ("CHECKING_UPDATES", r'\|\| HmiState : .*"Name":"CHECKING_FOR_UPDATES","State":3.*', 30, True, False, 0),
    ("UPDATE_FOUND", r'\|\| HmiNotification :.*"Name":"UPDATE_FOUND","Notification":2.*', 300, True, False, 0),
    ("ACTIVATION_POSSIBLE", r'\|\| HmiState :.*"Name":"ACTIVATION_POSSIBLE","State":9.*', 1200, False, False, 0),
    ("ACTIVATION_REBOOT", r'\|\| HmiState :.*"Name":"ACTIVATION_ABOUT_TO_REBOOT","State":23.*', 60, False, False, 0),
    ("VIPR_EXIT_CODE", r".*VIPR shutted down with VIPR-Exit-Code \[(\d+)\]", 600, False, False, 0, "VIPR", "VIPR"),
)
ADDITIONAL_PAYLOADS = (
    ("RECOVERY_REBOOT", r'\|\| HmiState :.*"Name":"RECOVERY_ABOUT_TO_REBOOT","State":30.*', 30, True, True, 30),
    ("POST_REBOOT", r'\|\| HmiState :.*"Name":"POSTPROCESSING_ABOUT_TO_REBOOT","State":.*', 30, True, True, 5),
    ("POST_PROCESS", r'\|\| HmiNotification :.*"Name":"POSTPROCESSING","Notification":10.*', 30, True, True, 10),
    (
        "VERSION",
        r"\|\| Detected expected platform version (IDC23_[a-zA-Z]?_?\d+w\d+.\d+-\d+)-\d+.*",
        30,
        True,
        True,
        0,
        "SUAG",
        "AGNT",
    ),
)
RSU_ERROR_PAYLOADS = ("PREPARATION_ERROR", r'\|\| HmiNotification : \{"Name":"PREPARATION_ERROR","Notification.*')
VERSION_AFTER_RSU = "IDC23_24w11.4-1"
