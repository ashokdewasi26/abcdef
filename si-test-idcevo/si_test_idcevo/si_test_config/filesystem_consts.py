# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Linux filesystem related Constant Variables"""

# Internal/External File System Configs
INT_EXT_FILE_SYSTEM_CONFIGS = [
    "CONFIG_EXT4_FS=y",
    "CONFIG_FAT_FS=y",
    "CONFIG_MSDOS_FS=y",
    "CONFIG_VFAT_FS=y",
]

SPECIAL_PURPOSE_FILE_SYSTEM_CONFIGS = [
    "CONFIG_SYSFS=y",
    "CONFIG_TMPFS=y",
    "CONFIG_KERNFS=y",
    "CONFIG_PROC_FS=y",
]

SECURITY_FILE_SYSTEM_CONFIGS = [
    "CONFIG_SECURITYFS=y",
    "CONFIG_DM_VERITY=y",
    "CONFIG_BLK_DEV_DM=y",
    "CONFIG_BLK_DEV_DM_BUILTIN=y",
]

EXPECTED_ROOT_FILESYSTEM = [
    "bin",
    "etc",
    "media",
    "root",
    "tmp",
    "boot",
    "home",
    "mnt",
    "run",
    "usr",
    "lib",
    "opt",
    "sbin",
    "var",
    "dev",
    "lost+found",
    "proc",
    "sys",
]

# EXPECTED_EXT4_MOUNT_DM0' keys: String that must be found in obtained output.
# EXPECTED_EXT4_MOUNT_DM0' items: Keywords that must be found, inside parenthesis, in the obtained output.
#                              The obtained output could contain more unexpected keywords.
EXPECTED_EXT4_MOUNTS_WITH_ECU = {
    "idcevo": [
        "/dev/mapper/cont_huapp on /opt/hu_applications type ext4 (ro,relatime,seclabel)",
        "/dev/mapper/cont_telematics on /opt/telematics type ext4 (ro,relatime,seclabel)",
    ],
    "cde": ["/dev/mapper/cont_rse on /opt/cde_applications type ext4 (ro,relatime,seclabel)"],
    "rse26": ["/dev/mapper/cont_rse on /opt/rse_applications type ext4 (ro,relatime,seclabel)"],
}


# EXPECTED_EXT4_MOUNT_SDE21' keys: String that must be found in obtained output.
# EXPECTED_EXT4_MOUNT_SDE21' items: Keywords that must be found, inside parenthesis, in the obtained output.
#                              The obtained output could contain more unexpected keywords.

EXPECTED_TMP_DIRECTORY_CONTENT = {
    "HWAbstractionApp": r"^HWAbstractionApp\..*",
    "NodeShutdownGuard": r".*\-NodeShutdownGuard\..*",
    "deletion-handler": r".*\-deletion-handler\..*",
    "early_skvs": r".*\-early_skvs\..*",
    "temperature-monitor": r".*\-temperature-monitor\..*",
    "timemand": r".*\-timemand\..*",
    "videoavbconfig": r".*\-videoavbconfig\..*",
}

# EXPECTED_TMPFS_MOUNT' keys: String that must be found in obtained output.
# EXPECTED_TMPFS_MOUNT' items: Keywords that must be found, inside parenthesis, in the obtained output.
#                              The obtained output could contain more unexpected keywords.
EXPECTED_TMPFS_MOUNT = {
    "devtmpfs on /dev type devtmpfs ": [
        "rw",
        "relatime",
        "seclabel",
        "size",
        "2127248k",
        "nr_inodes",
        "531812",
        "mode",
        "755",
    ],
    "tmpfs on /dev/shm type tmpfs ": ["rw", "nosuid", "nodev", "seclabel"],
    "tmpfs on /run type tmpfs ": [],
    "tmpfs on /sys/fs/cgroup type tmpfs ": [
        "ro",
        "nosuid",
        "nodev",
        "noexec",
        "seclabel",
        "size",
        "4096k",
        "nr_inodes",
        "1024",
        "mode",
        "755",
    ],
    "tmpfs on /tmp type tmpfs ": [
        "rw",
        "nodev",
        "noexec",
        "relatime",
        "rootcontext",
        "system_u:object_r:tmp_t",
        "seclabel",
    ],
    "tmpfs on /var/volatile type tmpfs ": [
        "rw",
        "noexec",
        "relatime",
        "rootcontext",
        "system_u:object_r:var_t",
        "seclabel",
    ],
}

EXPECTED_PROC_DIRECTORY_CONTENT = [
    "asound",
    "bootinfo",
    "boottime",
    "buddyinfo",
    "bus",
    "cgroups",
    "cmdline",
    "config.gz",
    "consoles",
    "cpuinfo",
    "crypto",
    "device-tree",
    "devices",
    "diskstats",
    "dram_bootlog",
    "driver",
    "dss_kmsg",
    "execdomains",
    "filesystems",
    "first_kmsg",
    "fs",
    "harman_eavb_mac",
    "interrupts",
    "iomem",
    "ioports",
    "irq",
    "kallsyms",
    "key-users",
    "keys",
    "kmsg",
    "kpagecgroup",
    "kpagecount",
    "kpageflags",
    "loadavg",
    "locks",
    "meminfo",
    "misc",
    "modules",
    "mounts",
    "net",
    "nk",
    "pagetypeinfo",
    "partitions",
    "pressure",
    "schedstat",
    "self",
    "softirqs",
    "stat",
    "sys",
    "sysvipc",
    "thread-self",
    "timer_list",
    "tty",
    "uptime",
    "version",
    "vgki",
    "vmallocinfo",
    "vmstat",
    "zoneinfo",
]

EXPECTED_SYSFS_DIRECTORY_CONTENT = [
    "block",
    "class",
    "devices",
    "fs",
    "module",
    "power",
    "bus",
    "dev",
    "firmware",
    "kernel",
    "nk",
]
