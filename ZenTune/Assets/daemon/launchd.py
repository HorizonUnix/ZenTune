# ZenTune/Assets/daemon/launchd.py
from __future__ import annotations

import os
import subprocess

from Assets.core import config as cfg
from Assets.daemon import service as common

LABEL = "com.horizonunix.zentune"
PLIST_FILE = f"/Library/LaunchDaemons/{LABEL}.plist"
LOG_FILE = f"/var/log/{cfg.APP_NAME}.log"


def is_available() -> bool:
    return subprocess.call(
        ["launchctl", "print", "system"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def _render_plist() -> str:
    python = common.python_bin()
    script = common.daemon_script()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '  <key>Label</key>\n'
        f'  <string>{LABEL}</string>\n'
        '  <key>ProgramArguments</key>\n'
        '  <array>\n'
        f'    <string>{python}</string>\n'
        f'    <string>{script}</string>\n'
        '  </array>\n'
        '  <key>RunAtLoad</key>\n'
        '  <true/>\n'
        '  <key>KeepAlive</key>\n'
        '  <dict>\n'
        '    <key>SuccessfulExit</key>\n'
        '    <false/>\n'
        '  </dict>\n'
        '  <key>StandardOutPath</key>\n'
        f'  <string>{LOG_FILE}</string>\n'
        '  <key>StandardErrorPath</key>\n'
        f'  <string>{LOG_FILE}</string>\n'
        '</dict>\n'
        '</plist>\n'
    )


def _launchctl(*args: str) -> int:
    return common.sudo_run("launchctl", *args)


def install_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not common.ensure_venv():
        return {"ok": False, "error": "Could not prepare the daemon environment."}
    if not common.sudo_write_file(PLIST_FILE, _render_plist(), ".plist", owner="root:wheel"):
        return {"ok": False, "error": "Failed to write the service file."}
    if _launchctl("bootstrap", "system", PLIST_FILE) != 0:
        return {"ok": False, "error": "Daemon installed, but the service failed to start."}
    return {"ok": True, "warning": ""}


def uninstall_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    _launchctl("bootout", f"system/{LABEL}")
    common.sudo_run("rm", "-f", PLIST_FILE)
    return {"ok": True}


def service_running() -> bool:
    if not os.path.isfile(PLIST_FILE):
        return False
    out = subprocess.run(
        ["launchctl", "print", f"system/{LABEL}"],
        capture_output=True, text=True,
    )
    return out.returncode == 0 and "state = running" in out.stdout


def service_enabled() -> bool:
    return os.path.isfile(PLIST_FILE)


def restart_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if _launchctl("kickstart", "-k", f"system/{LABEL}") != 0:
        return {"ok": False, "error": "Failed to restart the service."}
    return {"ok": True}


def read_logs(lines: int = 200) -> str:
    try:
        with open(LOG_FILE) as f:
            content = f.readlines()
    except OSError:
        return "No daemon logs yet."
    tail = content[-lines:]
    text = "".join(tail).strip()
    return text or "No daemon logs yet."


def service_path_stale() -> bool:
    if not os.path.isfile(PLIST_FILE):
        return False
    try:
        with open(PLIST_FILE) as f:
            content = f.read()
    except OSError:
        return False
    return not (f"<string>{common.python_bin()}</string>" in content
                and f"<string>{common.daemon_script()}</string>" in content)


def regenerate_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not common.sudo_write_file(PLIST_FILE, _render_plist(), ".plist", owner="root:wheel"):
        return {"ok": False, "error": "Failed to write the service file."}
    _launchctl("bootout", f"system/{LABEL}")
    if _launchctl("bootstrap", "system", PLIST_FILE) != 0:
        return {"ok": False, "error": "Service file updated, but the daemon failed to restart."}
    return {"ok": True}
