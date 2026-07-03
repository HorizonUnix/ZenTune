from __future__ import annotations

import glob
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from Assets.core import platform as plat

log = logging.getLogger(__name__)

HWMON_GLOB = "/sys/class/hwmon/hwmon*"
DRM_GLOB = "/sys/class/drm/card*/device"
PROC_STAT = "/proc/stat"
PROC_CPUINFO = "/proc/cpuinfo"

_cache = {}
_load_state = {"prev": None}


@dataclass
class SensorSample:
    cpu_temp: Optional[float] = None
    cpu_load: Optional[float] = None
    cpu_power: Optional[float] = None
    cpu_clk: Optional[float] = None
    igpu_load: Optional[float] = None
    igpu_clk: Optional[float] = None
    mem_clk: Optional[float] = None


def reset_cache():
    _cache.clear()
    _load_state["prev"] = None


def _read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _find_hwmon(name):
    key = ("hwmon", name)
    if key not in _cache:
        found = None
        for hwmon in sorted(glob.glob(HWMON_GLOB)):
            if _read_text(os.path.join(hwmon, "name")) == name:
                found = hwmon
                break
        _cache[key] = found
    return _cache[key]


def _find_amdgpu_card():
    key = ("amdgpu",)
    if key not in _cache:
        found = None
        for device in sorted(glob.glob(DRM_GLOB)):
            uevent = _read_text(os.path.join(device, "uevent")) or ""
            if "DRIVER=amdgpu" in uevent and os.path.exists(os.path.join(device, "gpu_busy_percent")):
                found = device
                break
        _cache[key] = found
    return _cache[key]


def _cpu_temp():
    hwmon = _find_hwmon("k10temp")
    if hwmon is None:
        return None
    node = None
    for label in sorted(glob.glob(os.path.join(hwmon, "temp*_label"))):
        if _read_text(label) in ("Tctl", "Tdie"):
            m = re.match(r"^temp(\d+)_label$", os.path.basename(label))
            if m:
                node = os.path.join(hwmon, f"temp{m.group(1)}_input")
                break
    if node is None:
        node = os.path.join(hwmon, "temp1_input")
    raw = _read_text(node)
    try:
        return int(raw) / 1000.0
    except (TypeError, ValueError):
        return None


def _cpu_power():
    hwmon = _find_hwmon("amdgpu")
    if hwmon is None:
        return None
    for label in sorted(glob.glob(os.path.join(hwmon, "power*_label"))):
        if _read_text(label) == "PPT":
            match = re.fullmatch(r"(power\d+)_label", os.path.basename(label))
            if not match:
                continue
            raw = _read_text(os.path.join(hwmon, f"{match.group(1)}_input"))
            try:
                return int(raw) / 1000000.0
            except (TypeError, ValueError):
                return None
    return None


def _cpu_clk():
    text = _read_text(PROC_CPUINFO)
    if not text:
        return None
    values = [float(m) for m in re.findall(r"cpu MHz\s*:\s*([\d.]+)", text)]
    return sum(values) / len(values) if values else None


def _cpu_load():
    text = _read_text(PROC_STAT)
    if not text:
        return None
    parts = text.splitlines()[0].split()[1:]
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return None
    if len(nums) < 5:
        return None
    idle = nums[3] + nums[4]
    total = sum(nums)
    previous = _load_state["prev"]
    _load_state["prev"] = (total, idle)
    if previous is None or total <= previous[0]:
        return None
    return (1.0 - (idle - previous[1]) / (total - previous[0])) * 100.0


def _current_clk(path):
    text = _read_text(path)
    if not text:
        return None
    for line in text.splitlines():
        if "*" in line:
            match = re.search(r"(\d+)\s*MHz", line, re.IGNORECASE)
            if match:
                return float(match.group(1))
    return None


def _igpu_load():
    card = _find_amdgpu_card()
    if card is None:
        return None
    raw = _read_text(os.path.join(card, "gpu_busy_percent"))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _igpu_clk():
    card = _find_amdgpu_card()
    if card is None:
        return None
    return _current_clk(os.path.join(card, "pp_dpm_sclk"))


def igpu_max_clock():
    key = ("igpu_max_clk",)
    if key not in _cache:
        card = _find_amdgpu_card()
        if card is None:
            _cache[key] = None
        else:
            text = _read_text(os.path.join(card, "pp_dpm_sclk")) or ""
            values = [float(m) for m in re.findall(r"(\d+)\s*MHz", text, re.IGNORECASE)]
            _cache[key] = max(values) if values else None
    return _cache[key]


def _mem_clk():
    card = _find_amdgpu_card()
    if card is None:
        return None
    return _current_clk(os.path.join(card, "pp_dpm_mclk"))


def _reconcile(trusted, secondary, tolerance, label):
    if trusted is None:
        return secondary
    if secondary is not None:
        diff = abs(trusted - secondary)
        if diff > tolerance:
            log.debug(
                "pm_table %s cross-check exceeded tolerance: "
                "diff=%s tolerance=%s (keeping hwmon value)",
                label,
                diff,
                tolerance,
            )
    return trusted


def _read_pmtable():
    from Assets.core import hardware as hw
    from zenmaster.smu import read_pm_sensors
    return read_pm_sensors(hw.detected_family())


def sample():
    if plat.IS_MACOS:
        return SensorSample()
    pm = _read_pmtable()
    temp = _reconcile(_cpu_temp(), pm.tctl_temp if pm else None, 5.0, "cpu_temp")
    load = _reconcile(_cpu_load(), pm.cclk_busy if pm else None, 15.0, "cpu_load")
    pm_power = None
    if pm is not None:
        pm_power = pm.socket_power if pm.socket_power is not None else pm.stapm_value
    power = _reconcile(_cpu_power(), pm_power, 5.0, "cpu_power")
    igpu_clk = _reconcile(_igpu_clk(), pm.gfx_clk if pm else None, 200.0, "igpu_clk")
    return SensorSample(
        cpu_temp=temp,
        cpu_load=load,
        cpu_power=power,
        cpu_clk=_cpu_clk(),
        igpu_load=_igpu_load(),
        igpu_clk=igpu_clk,
        mem_clk=_mem_clk(),
    )


def capabilities():
    if plat.IS_MACOS:
        return set()
    snapshot = sample()
    caps = set()
    if snapshot.cpu_temp is not None:
        caps.add("cpu_temp")
    if snapshot.cpu_power is not None:
        caps.add("cpu_power")
    if snapshot.cpu_clk is not None:
        caps.add("cpu_clk")
    if _read_text(PROC_STAT):
        caps.add("cpu_load")
    if snapshot.igpu_load is not None:
        caps.add("igpu_load")
    if snapshot.igpu_clk is not None:
        caps.add("igpu_clk")
    return caps
