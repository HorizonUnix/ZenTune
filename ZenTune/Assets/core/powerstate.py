from __future__ import annotations

import os
import subprocess

from Assets.core import platform as plat

_AC_TYPES = frozenset({"Mains", "USB", "USB_C", "USB_PD", "USB_PD_DRP", "USB_C_DRP"})


def _on_ac_linux() -> bool:
    ac_online = False
    found_ac = False
    battery_discharging = False
    try:
        for entry in os.listdir("/sys/class/power_supply"):
            base = f"/sys/class/power_supply/{entry}"
            try:
                with open(f"{base}/type") as f:
                    ptype = f.read().strip()
            except OSError:
                continue
            if ptype in _AC_TYPES:
                found_ac = True
                try:
                    with open(f"{base}/online") as f:
                        if f.read().strip() == "1":
                            ac_online = True
                except OSError:
                    pass
            elif ptype == "Battery":
                try:
                    with open(f"{base}/status") as f:
                        if f.read().strip().lower() == "discharging":
                            battery_discharging = True
                except OSError:
                    pass
    except Exception:
        pass
    if found_ac:
        return ac_online
    return not battery_discharging


def _on_ac_macos() -> bool:
    try:
        out = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    first_line = (out.stdout or "").splitlines()[0] if out.stdout else ""
    if "AC Power" in first_line:
        return True
    if "Battery Power" in first_line:
        return False
    return True


def on_ac() -> bool:
    if plat.IS_MACOS:
        return _on_ac_macos()
    return _on_ac_linux()
