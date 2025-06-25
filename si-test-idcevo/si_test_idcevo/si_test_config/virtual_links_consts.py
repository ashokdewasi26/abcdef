# Copyright (C) 2024. BMW CTW PT. All rights reserved.

BUFQ_EXPECTED_CONTENT = [
    r"bufq,0 serv 3/OFF/'be,32,vbufq-VM3' cli 2/OFF/'' paddr .*",
    r"bufq,0 serv 2/OFF/'' cli 3/OFF/'be,32,vbufq-VM3' paddr .*",
    r"bufq,1 serv 2/ON/'be,32,vbufq-VM2' cli 3/ON/'' paddr .*",
    r"bufq,1 serv 3/ON/'' cli 2/ON/'be,32,vbufq-VM2' paddr .*",
]

PDEV_EXPECTED_CONTENT = [
    r"PDEV used: .* \(.* bytes\)",
]

VABOX_EXPECTED_CONTENT = [
    r"vabox,0 serv 2/ON/'virtual abox' cli 3/ON/'vm3 virtual abox' paddr .*",
]

VBPIPE_EXPECTED_CONTENT = [
    r"vbpipe,0 serv 2/OFF/';;;;name=vbpipe1' cli 3/OFF/';;;;name=vbpipe1' paddr .*",
    r"vbpipe,0 serv 3/OFF/';;;;name=vbpipe1' cli 2/OFF/';;;;name=vbpipe1' paddr .*",
    r"vbpipe,1 serv 2/OFF/';;;;name=vbpipe10' cli 3/OFF/';;;;name=vbpipe10' paddr .*",
    r"vbpipe,1 serv 3/OFF/';;;;name=vbpipe10' cli 2/OFF/';;;;name=vbpipe10' paddr .*",
    r"vbpipe,2 serv 2/OFF/';;;;name=vbpipe11' cli 3/OFF/';;;;name=vbpipe11' paddr .*",
    r"vbpipe,2 serv 3/OFF/';;;;name=vbpipe11' cli 2/OFF/';;;;name=vbpipe11' paddr .*",
    r"vbpipe,3 serv 2/OFF/';;;;name=vbpipe12' cli 3/OFF/';;;;name=vbpipe12' paddr .*",
    r"vbpipe,3 serv 3/OFF/';;;;name=vbpipe12' cli 2/OFF/';;;;name=vbpipe12' paddr .*",
    r"vbpipe,4 serv 2/OFF/';;;;name=vbpipe13' cli 3/OFF/';;;;name=vbpipe13' paddr .*",
    r"vbpipe,4 serv 3/OFF/';;;;name=vbpipe13' cli 2/OFF/';;;;name=vbpipe13' paddr .*",
]

VDELAY_EXPECTED_CONTENT = [
    r"vdelay,0 serv 2/RST/'100' cli 3/OFF/'' paddr .*",
]

VDMA_EXPECTED_CONTENT = [
    r"vdma_engine,0 serv 2/OFF/'' cli 3/OFF/'' paddr .*",
]

VETH2_EXPECTED_CONTENT = [
    r"veth2,0 serv 2/ON/',vnet23_0' cli 3/ON/',vnet32_0' paddr .*",
    r"veth2,0 serv 3/ON/',vnet32_0' cli 2/ON/',vnet23_0' paddr .*",
]

VFENCE2_EXPECTED_CONTENT = [
    r"vfence2,0 serv 2/OFF/'' cli 2/OFF/'' paddr .*",
    r"vfence2,1 serv 2/OFF/'' cli 3/OFF/'' paddr .*",
    r"vfence2,1 serv 3/OFF/'' cli 2/OFF/'' paddr .*",
]

VIPC_EXPECTED_CONTENT = [
    r"vipc_test,0 serv 2/OFF/'vipc_test' cli 3/OFF/'' paddr .*",
    r"vipc_test,0 serv 3/OFF/'' cli 2/OFF/'vipc_test' paddr .*",
]

VGPU_EXPECTED_CONTENT = [
    r"vgpu-arb-comm,0 serv 2/ON/'' cli 3/ON/'' paddr .*",
    r"vgpu-arb-comm,0 serv 3/ON/'' cli 2/ON/'' paddr .*",
    r"vgpu-arb-comm,1 serv 2/ON/'' cli 2/ON/'' paddr .*",
    r"vgpu-arb-comm,1 serv 2/ON/'' cli 2/ON/'' paddr .*",
]

VL_EXPECTED_CONTENT = [
    r"vl,evt-stats,0 serv 1/ON/'' cli 2/ON/'' paddr .*",
    r"vl,evt-log,0 serv 1/ON/'' cli 2/ON/'' paddr .*",
    r"vl,virtio-bus,0 serv 1/ON/'' cli 2/ON/'' paddr .*",
    r"vl,hypevent.v1,0 serv 1/ON/'vproperty' cli 2/ON/'' paddr .*",
]

VMQ_EXPECTED_CONTENT = [
    r"vmq_test,0 serv 2/OFF/'vmq_test' cli 3/OFF/'' paddr .*",
    r"vmq_test,0 serv 3/OFF/'' cli 2/OFF/'vmq_test' paddr .*",
]

VNPU_EXPECTED_CONTENT = [
    r"vnpu,0 serv 2/ON/'be' cli 3/ON/'fe' paddr .*",
    r"vnpu,0 serv 3/ON/'fe' cli 2/ON/'be' paddr .*",
]

VPCI_EXPECTED_CONTENT = [
    r"vpci,0 serv 2/OFF/'vpci_ctrl' cli 3/OFF/'vpci_ctrl' paddr .*",
]

VRPC_EXPECTED_CONTENT = [
    r"vrpc,5 serv 3/OFF/'vtrustonic_ivi cb' cli 2/OFF/'vtrustonic_ivi cb' paddr .*",
    r"vrpc,6 serv 2/ON/'vclk_ctrl' cli 3/ON/'vclk_ctrl' paddr .*",
    r"vrpc,13 serv 2/OFF/'vsmfcenc,2k' cli 3/OFF/'vsmfcenc' paddr .*",
    r"vrpc,14 serv 2/OFF/'vsmfcdec,2k' cli 3/OFF/'vsmfcdec' paddr .*",
    r"vrpc,16 serv 2/OFF/'vtrustonic_ivi' cli 3/OFF/'vtrustonic_ivi' paddr .*",
]

VVIDEO2_EXPECTED_CONTENT = [
    r"vvideo2,0 serv 2/ON/'be' cli 3/ON/'fe vvideo2=\(s5p-mfc-dec0,6\) vvideo2=\(s5p-mfc-enc0,7\) "
    r"vvideo2=\(s5p-mfc-dec-secure0,8\) vvideo2=\(s5p-mfc-enc-secure0,9\) vvideo2=\(s5p-mfc-enc-otf0,10\)"
    r" vvideo2=\(s5p-mfc-enc-otf-secure0,11\) ' paddr .*",
    r"vvideo2,0 serv 3/ON/'fe vvideo2=\(s5p-mfc-dec0,6\) vvideo2=\(s5p-mfc-enc0,7\) vvideo2=\(s5p-mfc-dec-secure0,8\)"
    r" vvideo2=\(s5p-mfc-enc-secure0,9\) vvideo2=\(s5p-mfc-enc-otf0,10\) "
    r"vvideo2=\(s5p-mfc-enc-otf-secure0,11\) ' cli 2/ON/'be' paddr .*",
]

VLINK_EXPECTED_CONTENT = {
    "bufq": BUFQ_EXPECTED_CONTENT,
    "pdev": PDEV_EXPECTED_CONTENT,
    "vabox": VABOX_EXPECTED_CONTENT,
    "vbpipe": VBPIPE_EXPECTED_CONTENT,
    "vdelay": VDELAY_EXPECTED_CONTENT,
    "vdma": VDMA_EXPECTED_CONTENT,
    "veth2": VETH2_EXPECTED_CONTENT,
    "vfence2": VFENCE2_EXPECTED_CONTENT,
    "vipc": VIPC_EXPECTED_CONTENT,
    "vgpu": VGPU_EXPECTED_CONTENT,
    "vl": VL_EXPECTED_CONTENT,
    "vmq": VMQ_EXPECTED_CONTENT,
    "vnpu": VNPU_EXPECTED_CONTENT,
    "vpci": VPCI_EXPECTED_CONTENT,
    "vrpc": VRPC_EXPECTED_CONTENT,
    "vvideo2": VVIDEO2_EXPECTED_CONTENT,
}

VEVENT0_EXPECTED_CONTENT = [
    r"vevent,0 serv 2/status/'bootargs:idev_bustype!=\(u16\)6&&\(idev_evbit\[0\]&\(u32\)0x2\)!=\(u32\)0&&"
    r"\(idev_keybit\[3\]&\(u32\)0x100000\)!=\(u32\)0&&\(idev_keybit\[0\]&\(u32\)0x100\)==\(u32\)0:2,3,4:DEFAULT"
    r"-focus;\(idev_evbit\[0\]&\(u32\)0x20\)!=\(u32\)0&&\(idev_swbit\[0\]&\(u32\)0x14\)!=\(u32\)0:2,3,4:SW-broadcast"
    r"\|DEFAULT-focus;\(idev_evbit\[0\]&\(u32\)0x2\)!=\(u32\)0&&idev_keybit\[0..7\]!=\(u32\)\{0,0,0,0,0,0,0,0\}:2,3,4"
    r":DEFAULT-focus;\(idev_evbit\[0\]&\(u32\)0x4\)!=\(u32\)0&&\(idev_relbit\[0\]&\(u32\)0x3\)==\(u32\)0x3:2,3,4:"
    r"DEFAULT-focus;\(idev_evbit\[0\]&\(u32\)0x8\)!=\(u32\)0&&\(idev_absbit\[1\]&\(u32\)0x318000\)==\(u32\)0x318000:"
    r"2,3,4:DEFAULT-focus;true:2,3,4:DEFAULT-focus;' cli 3/status/'' paddr .*",
    r"vevent,0 serv 2/status/'bootargs:idev_bustype!=\(u16\)6&&\(idev_evbit\[0\]&\(u32\)0x2\)!=\(u32\)0&&"
    r"\(idev_keybit\[3\]&\(u32\)0x100000\)!=\(u32\)0&&\(idev_keybit\[0\]&\(u32\)0x100\)==\(u32\)0:2,3,4:DEFAULT"
    r"-focus;\(idev_evbit\[0\]&\(u32\)0x20\)!=\(u32\)0&&\(idev_swbit\[0\]&\(u32\)0x14\)!=\(u32\)0:2,3,4:SW-broadcast"
    r"|DEFAULT-focus;\(idev_evbit[0]&\(u32\)0x2\)!=\(u32\)0&&idev_keybit\[0..7\]!=\(u32\)\{0,0,0,0,0,0,0,0\}:"
    r"2,3,4:DEFAULT-focus;\(idev_evbit\[0\]&\(u32\)0x4\)!=\(u32\)0&&\(idev_relbit\[0\]&\(u32\)0x3\)==\(u32\)0x3:2,3,4"
    r":DEFAULT-focus;\(idev_evbit\[0\]&\(u32\)0x8\)!=\(u32\)0&&\(idev_absbit\[1\]&\(u32\)0x318000\)==\(u32\)0x318000"
    r":2,3,4:DEFAULT-focus;true:2,3,4:DEFAULT-focus;' cli 2/OFF/'' paddr .*",
]
