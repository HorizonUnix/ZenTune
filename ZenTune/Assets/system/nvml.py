from __future__ import annotations

import ctypes


def open_session():
    try:
        lib = ctypes.CDLL("libnvidia-ml.so.1")
    except OSError:
        return None
    lib.nvmlInit_v2.restype = ctypes.c_int
    lib.nvmlShutdown.restype = ctypes.c_int
    if lib.nvmlInit_v2() != 0:
        return None
    return lib
