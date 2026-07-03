from __future__ import annotations

import atexit
import fcntl
import logging
import os
import time
from dataclasses import dataclass

from Assets.core import config as cfg
from Assets.core import platform as plat
from Assets.core.platform import RUNTIME_DIR
from Assets.core.powerstate import on_ac as _on_ac

_DAEMON_LOCK_FILE = f"{RUNTIME_DIR}/{cfg.APP_NAME}_daemon.lock"

log = logging.getLogger(cfg.APP_NAME)


def _clock_boottime() -> float:
    if plat.IS_MACOS:
        return time.time()
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _acquire_daemon_lock() -> bool:
    lock_fh = None
    try:
        lock_fh = open(_DAEMON_LOCK_FILE, "w")
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fh.write(str(os.getpid()))
        lock_fh.flush()
        atexit.register(lock_fh.close)
        return True
    except (IOError, OSError):
        if lock_fh is not None:
            lock_fh.close()
        return False


def _load_builtin_presets() -> dict:
    from Assets.tuning.power import get_presets
    return get_presets()


def _resolve_preset_args(preset_name: str) -> tuple[str, str] | None:
    presets = _load_builtin_presets()
    if preset_name in presets:
        return preset_name, presets[preset_name]

    base = preset_name.removesuffix("_custom_preset")
    try:
        from Assets.tuning.custom import load_custom_presets, preset_to_args
        for p in load_custom_presets():
            if p["name"] == base:
                return preset_name, preset_to_args(p)
    except Exception as exc:
        log.debug("Failed to load custom preset %r: %s", preset_name, exc)

    return None


def _dn(name: str) -> str:
    return name.removesuffix("_custom_preset") if name else "none"


def _fmt_duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


_smu_state = {"warned": False}


def _apply_via_smu(args: str, mode: str) -> tuple[str, bool]:
    from zenmaster.smu import unavailable_reason
    from Assets.core import hardware as hw
    family = hw.detected_family()
    if not args.strip():
        return "", False
    if not family or family == "Unknown":
        log.error("Cannot apply preset: CPU family not detected.")
        return "", False
    blocked = unavailable_reason()
    if blocked:
        if not _smu_state["warned"]:
            _smu_state["warned"] = True
            log.error("%s. Presets cannot be applied.\nInstall guide: %s", blocked, cfg.RYZEN_SMU_WIKI_URL)
        return f"{blocked}, preset not applied", False
    if _smu_state["warned"]:
        _smu_state["warned"] = False
        log.info("ryzen_smu is available again, presets can be applied.")
    try:
        from Assets.engine import runner
        output, rejected = runner.apply_args(args, family)
        if rejected:
            log.warning(
                "Preset '%s' applied, but the SMU rejected one or more commands:\n%s",
                _dn(mode), output,
            )
        else:
            log.debug("SMU apply (%s/%s):\n%s", mode, family, output)
        return output, rejected
    except Exception as exc:
        log.error("Failed to apply preset '%s': %s", _dn(mode), exc)
        return "", False


@dataclass
class PresetState:
    mode: str
    args: str
    automation: bool
    interval: int
    reapply: bool


def _load_saved_preset() -> PresetState | None:
    cfg.load()
    user_mode = cfg.get("User", "Mode")
    on_ac = cfg.get("Automations", "OnAC", "")
    on_battery = cfg.get("Automations", "OnBattery", "")
    automation = bool(on_ac or on_battery)

    result = _resolve_preset_args(user_mode)
    if result:
        _, args = result
    elif automation:
        args = ""
        log.debug(
            "Base preset '%s' not found; automation slots will manage switching.",
            user_mode,
        )
    else:
        log.error("Preset '%s' not found, cannot apply.", user_mode)
        return None

    reapply = cfg.get("Settings", "ReApply", "0") == "1"
    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)

    return PresetState(
        mode=user_mode,
        args=args,
        automation=automation,
        interval=interval,
        reapply=reapply,
    )

