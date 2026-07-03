from __future__ import annotations

import ctypes
import fcntl
import os

NV_IOCTL_MAGIC = ord("F")
NV_ESC_REGISTER_FD = 201
NV_ESC_RM_CONTROL = 0x2A
NV_ESC_RM_ALLOC = 0x2B
NV01_DEVICE_0 = 0x80
NV20_SUBDEVICE_0 = 0x2080
CMD_GR_GET_ROP_INFO = 0x20801213
_IOC_WRITE = 1
_IOC_READ = 2


def _rw(nr: int, size: int) -> int:
    direction = _IOC_READ | _IOC_WRITE
    return ((direction << 30) | (size << 16) | (NV_IOCTL_MAGIC << 8) | nr) & 0xFFFFFFFF


class _NVOS21(ctypes.Structure):
    _fields_ = [("hRoot", ctypes.c_uint32), ("hObjectParent", ctypes.c_uint32),
                ("hObjectNew", ctypes.c_uint32), ("hClass", ctypes.c_uint32),
                ("pAllocParms", ctypes.c_void_p), ("paramsSize", ctypes.c_uint32),
                ("status", ctypes.c_int32)]


class _NVOS64(ctypes.Structure):
    _fields_ = [("hRoot", ctypes.c_uint32), ("hObjectParent", ctypes.c_uint32),
                ("hObjectNew", ctypes.c_uint32), ("hClass", ctypes.c_uint32),
                ("pAllocParms", ctypes.c_void_p), ("pRightsRequested", ctypes.c_void_p),
                ("paramsSize", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("status", ctypes.c_int32)]


class _NVOS54(ctypes.Structure):
    _fields_ = [("hClient", ctypes.c_uint32), ("hObject", ctypes.c_uint32),
                ("cmd", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("params", ctypes.c_void_p), ("paramsSize", ctypes.c_uint32),
                ("status", ctypes.c_int32)]


class _ROPInfo(ctypes.Structure):
    _fields_ = [("ropUnitCount", ctypes.c_uint32), ("ropOperationsFactor", ctypes.c_uint32),
                ("ropOperationsCount", ctypes.c_uint32)]


def _call(fd: int, nr: int, struct) -> int:
    return fcntl.ioctl(fd, _rw(nr, ctypes.sizeof(struct)), struct, True)


def get_rop_info(index: int = 0) -> tuple[int, int, int] | None:
    try:
        ctl = os.open("/dev/nvidiactl", os.O_RDWR)
    except OSError:
        return None
    try:
        client = _NVOS21()
        if _call(ctl, NV_ESC_RM_ALLOC, client) != 0 or client.status != 0:
            return None
        hclient = client.hObjectNew
        try:
            node = os.open(f"/dev/nvidia{index}", os.O_RDWR | os.O_CLOEXEC)
        except OSError:
            return None
        try:
            ctl_handle = ctypes.c_int(ctl)
            fcntl.ioctl(node, _rw(NV_ESC_REGISTER_FD, ctypes.sizeof(ctl_handle)), ctl_handle, True)

            device_params = (ctypes.c_ubyte * 64)()
            device = _NVOS64(hRoot=hclient, hObjectParent=hclient, hObjectNew=0xB1000000,
                             hClass=NV01_DEVICE_0, paramsSize=0, flags=0, status=0)
            device.pAllocParms = ctypes.addressof(device_params)
            if _call(ctl, NV_ESC_RM_ALLOC, device) != 0 or device.status != 0:
                return None

            subdevice_params = (ctypes.c_ubyte * 8)()
            subdevice = _NVOS64(hRoot=hclient, hObjectParent=0xB1000000, hObjectNew=0xB2000000,
                                hClass=NV20_SUBDEVICE_0, paramsSize=0, flags=0, status=0)
            subdevice.pAllocParms = ctypes.addressof(subdevice_params)
            if _call(ctl, NV_ESC_RM_ALLOC, subdevice) != 0 or subdevice.status != 0:
                return None

            rop = _ROPInfo()
            control = _NVOS54(hClient=hclient, hObject=0xB2000000, cmd=CMD_GR_GET_ROP_INFO,
                              flags=0, paramsSize=ctypes.sizeof(rop), status=0)
            control.params = ctypes.addressof(rop)
            if _call(ctl, NV_ESC_RM_CONTROL, control) != 0 or control.status != 0:
                return None
            return (rop.ropUnitCount, rop.ropOperationsFactor, rop.ropOperationsCount)
        finally:
            os.close(node)
    finally:
        os.close(ctl)


def _expected_rops(name: str) -> int:
    if "Laptop" in name:
        if "5090" in name:
            return 112
        if "5080" in name:
            return 96
        if "5070 Ti" in name:
            return 64
        if "5070" in name:
            return 48
        if "4090" in name:
            return 112
        if "4080" in name:
            return 80
        if "4070" in name:
            return 48
        if "4060" in name:
            return 48
        if "4050" in name:
            return 48
    else:
        if "5090" in name:
            return 176
        if "5080" in name:
            return 112
        if "5070 Ti" in name:
            return 96
        if "5070" in name:
            return 64
        if "4090" in name:
            return 176
        if "4080" in name:
            return 112
        if "4070 Ti Super" in name:
            return 96
        if "4070 Ti" in name:
            return 80
        if "4070 Super" in name:
            return 80
        if "4070" in name:
            return 64
        if "4060 Ti" in name:
            return 48
        if "4060" in name:
            return 48
    return -1


def _nvml():
    from Assets.system.nvml import open_session
    return open_session()


def _device_count(lib) -> int:
    fn = getattr(lib, "nvmlDeviceGetCount_v2", None) or getattr(lib, "nvmlDeviceGetCount", None)
    if fn is None:
        return 0
    fn.restype = ctypes.c_int
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint)]
    count = ctypes.c_uint(0)
    return count.value if fn(ctypes.byref(count)) == 0 else 0


def _device_name(lib, index: int) -> str:
    get_dev = lib.nvmlDeviceGetHandleByIndex_v2
    get_dev.restype = ctypes.c_int
    get_dev.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
    dev = ctypes.c_void_p()
    if get_dev(index, ctypes.byref(dev)) != 0:
        return ""
    name = ctypes.create_string_buffer(96)
    if lib.nvmlDeviceGetName(dev, name, 96) != 0:
        return ""
    return name.value.decode(errors="ignore")


def check_rops() -> list[tuple[str, int, int]]:
    lib = _nvml()
    if lib is None:
        return []
    defective = []
    try:
        for index in range(_device_count(lib)):
            info = get_rop_info(index)
            if info is None:
                continue
            actual = info[2]
            name = _device_name(lib, index)
            if not name:
                continue
            expected = _expected_rops(name)
            if expected > 0 and actual < expected:
                defective.append((name, actual, expected))
    finally:
        lib.nvmlShutdown()
    return defective
