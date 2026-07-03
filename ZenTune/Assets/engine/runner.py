from __future__ import annotations

import shlex


def _nvml_apply(max_clk: int, core_offset: int, mem_offset: int,
                power_limit: int, lines: list[str]) -> None:
    import ctypes

    try:
        lib = ctypes.CDLL("libnvidia-ml.so.1")
    except OSError:
        lines.append("nvidia-clocks -> libnvidia-ml.so.1 not found")
        return

    NVML_ERROR_NOT_SUPPORTED = 3
    NVML_CLOCK_GRAPHICS = 0
    NVML_CLOCK_MEM = 2
    NVML_PSTATE_0 = 0

    class _ClockOffset(ctypes.Structure):
        _fields_ = [
            ("version",          ctypes.c_uint),
            ("type",             ctypes.c_uint),
            ("pstate",           ctypes.c_uint),
            ("clockOffsetMHz",   ctypes.c_int),
            ("minClockOffsetMHz",ctypes.c_int),
            ("maxClockOffsetMHz",ctypes.c_int),
        ]

    OFFSET_V1 = ctypes.sizeof(_ClockOffset) | (1 << 24)

    nvmlInit     = lib.nvmlInit_v2
    nvmlGetDev   = lib.nvmlDeviceGetHandleByIndex_v2
    nvmlShutdown = lib.nvmlShutdown
    nvmlInit.restype     = ctypes.c_int
    nvmlGetDev.restype   = ctypes.c_int
    nvmlShutdown.restype = ctypes.c_int
    nvmlGetDev.argtypes  = [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]

    init_rc = nvmlInit()
    if init_rc != 0:
        lines.append(f"nvidia-clocks -> nvmlInit failed (rc={init_rc})")
        return

    dev = ctypes.c_void_p()
    if nvmlGetDev(0, ctypes.byref(dev)) != 0:
        lines.append("nvidia-clocks -> nvmlDeviceGetHandleByIndex failed")
        nvmlShutdown()
        return

    if power_limit > 0:
        setPower = getattr(lib, "nvmlDeviceSetPowerManagementLimit", None)
        if setPower is None:
            lines.append("nvidia power-limit -> not supported by driver")
        else:
            setPower.restype = ctypes.c_int
            setPower.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            rc = setPower(dev, power_limit * 1000)
            if rc == 0:
                lines.append(f"nvidia power-limit -> {power_limit} W")
            elif rc == NVML_ERROR_NOT_SUPPORTED:
                lines.append("nvidia power-limit -> not supported by this GPU")
            else:
                lines.append(f"nvidia power-limit -> failed to set {power_limit} W (rc={rc})")

    if max_clk >= 4000:
        resetClk = getattr(lib, "nvmlDeviceResetGpuLockedClocks", None)
        if resetClk is None:
            lines.append("nvidia max-clock -> reset not supported by driver")
        else:
            resetClk.restype = ctypes.c_int
            resetClk.argtypes = [ctypes.c_void_p]
            rc = resetClk(dev)
            lines.append("nvidia max-clock -> reset" if rc == 0
                         else f"nvidia max-clock -> reset failed (rc={rc})")
    else:
        lockClk = getattr(lib, "nvmlDeviceSetGpuLockedClocks", None)
        if lockClk is None:
            lines.append("nvidia max-clock -> lock not supported by driver")
        else:
            lockClk.restype = ctypes.c_int
            lockClk.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
            rc = lockClk(dev, 0, max_clk)
            lines.append(f"nvidia max-clock -> {max_clk} MHz" if rc == 0
                         else f"nvidia max-clock -> failed to set {max_clk} MHz (rc={rc})")

    pairs = [(NVML_CLOCK_GRAPHICS, core_offset, "core"), (NVML_CLOCK_MEM, mem_offset, "mem")]
    used_modern = False

    setModern = getattr(lib, "nvmlDeviceSetClockOffsets", None)
    if setModern:
        setModern.restype = ctypes.c_int
        setModern.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ClockOffset)]
        for clock_type, offset, name in pairs:
            info = _ClockOffset()
            info.version = OFFSET_V1
            info.type = clock_type
            info.pstate = NVML_PSTATE_0
            info.clockOffsetMHz = offset
            rc = setModern(dev, ctypes.byref(info))
            if rc == NVML_ERROR_NOT_SUPPORTED:
                break
            used_modern = True
            suffix = "" if rc == 0 else f" (rc={rc})"
            lines.append(f"nvidia {name}-offset -> {offset} MHz{suffix}")

    if not used_modern:
        setGpc = getattr(lib, "nvmlDeviceSetGpcClkVfOffset", None)
        setMem = getattr(lib, "nvmlDeviceSetMemClkVfOffset", None)
        if setGpc:
            setGpc.restype = ctypes.c_int
            setGpc.argtypes = [ctypes.c_void_p, ctypes.c_int]
        if setMem:
            setMem.restype = ctypes.c_int
            setMem.argtypes = [ctypes.c_void_p, ctypes.c_int]
        for fn, offset, name in [(setGpc, core_offset, "core"), (setMem, mem_offset, "mem")]:
            if fn:
                rc = fn(dev, offset)
                suffix = "" if rc == 0 else f", rc={rc}"
                lines.append(f"nvidia {name}-offset -> {offset} MHz (legacy{suffix})")

    nvmlShutdown()


def _apply_nvidia(packed: str, lines: list[str]) -> None:
    parts = packed.split(",")
    if len(parts) not in (3, 4):
        lines.append("nvidia-clocks -> invalid format")
        return
    try:
        max_clk = int(parts[0])
        core_offset = int(parts[1])
        mem_offset = int(parts[2])
        power_limit = int(parts[3]) if len(parts) == 4 else 0
    except ValueError:
        lines.append("nvidia-clocks -> invalid values")
        return

    _nvml_apply(max_clk, core_offset, mem_offset, power_limit, lines)


def _apply_system(name: str, raw: int, lines: list[str]) -> None:
    from Assets.system import platformctl

    if name == "sys-power-profile":
        lines.append(platformctl.set_power_profile(raw))
    elif name == "sys-asus-mode":
        lines.append(platformctl.set_asus_mode(raw))
    elif name == "sys-asus-eco":
        lines.append(platformctl.set_asus_eco(raw))
    elif name == "sys-asus-mux":
        lines.append(platformctl.set_asus_mux(raw))
    elif name == "sys-ccd-affinity":
        lines.append(platformctl.set_ccd_affinity(raw))
    else:
        lines.append(f"{name} -> unknown system setting")


_CO_ARGS = {"set-coall", "set-coper", "set-cogfx"}


def apply_args(args_str: str, family: str) -> tuple[str, bool]:
    from zenmaster.apply import apply
    from zenmaster.smu import status_name

    try:
        tokens = shlex.split(args_str) if args_str.strip() else []
    except ValueError:
        return "invalid preset string (unclosed quote)", True

    lines: list[str] = []
    any_rejected = False
    smu_tokens: list[str] = []

    for token in tokens:
        bare = token.lstrip("-")
        if not bare:
            continue
        name, sep, val_str = bare.partition("=")
        if name == "nvidia-clocks":
            _apply_nvidia(val_str, lines)
        elif name.startswith("sys-"):
            try:
                raw = int(val_str, 0) if sep else 0
            except ValueError:
                lines.append(f"{name} -> invalid value '{val_str}'")
                continue
            _apply_system(name, raw, lines)
        else:
            if sep and name not in _CO_ARGS:
                try:
                    if int(val_str, 0) <= 0:
                        token = f"--{name}=0"
                except ValueError:
                    pass
            smu_tokens.append(token)

    if smu_tokens:
        results, rejected = apply(" ".join(smu_tokens), family)
        any_rejected = any_rejected or rejected
        for r in results:
            if r["error"]:
                lines.append(f"{r['arg']} -> {r['error']}")
            else:
                lines.append(
                    f"{r['arg']} [{r['mailbox']} 0x{r['opcode']:02X}] = {r['value']} -> "
                    f"{status_name(r['status'])}"
                )

    return "\n".join(lines) if lines else "(no matching commands for this family)", any_rejected
