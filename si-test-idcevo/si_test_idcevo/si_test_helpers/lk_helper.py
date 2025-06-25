def enter_lk_shell_instance(test_istance):
    """Method to enter LK shell instance
    Right now to enter LK shell is necessary to go to fastboot and write \x03 (^C)
    """
    test_istance.mtee_target.switch_to_fastboot()
    test_istance.mtee_target._console.write("\x03")


def boot_with_log_level(test_istance, level_value="00000000"):
    """
    This function can be used to set the boot log level in lk shell.
    param level_value: Pass the log level to increase or decrease the boot logging info.
    type level_value: str
    """
    boot_log_level_cmd = "boot --loglevel=" + level_value + "\n"
    test_istance.mtee_target._console.write(boot_log_level_cmd)
