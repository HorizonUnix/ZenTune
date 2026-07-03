# ZenTune/Assets/daemon/systemd.py
from __future__ import annotations

import os
import subprocess

from Assets.core import config as cfg
from Assets.daemon import service as common

SERVICE_NAME = f"{cfg.APP_NAME}.service"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}"

_available: bool | None = None


def is_available() -> bool:
    global _available
    if _available is None:
        _available = subprocess.call(
            ["systemctl", "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) == 0
    return _available


def _render_unit() -> str:
    return (
        "[Unit]\n"
        "Description=ZenTune Power Management Daemon\n"
        "After=multi-user.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={common.python_bin()} {common.daemon_script()}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "StandardOutput=journal\n"
        "StandardError=journal\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _systemctl(*args: str) -> int:
    if not is_available():
        return 1
    return common.sudo_run("systemctl", *args)


def install_service() -> dict:
    if not is_available():
        return {"ok": False, "manual": True,
                "error": f"systemctl is not available. Start the daemon manually:\n"
                         f"{common.manual_start_command()}"}
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not common.ensure_venv():
        return {"ok": False, "error": "Could not prepare the daemon environment."}
    if not common.sudo_write_file(SERVICE_FILE, _render_unit(), ".service"):
        return {"ok": False, "error": "Failed to write the service file."}
    _systemctl("daemon-reload")
    warning = ""
    if _systemctl("enable", SERVICE_NAME) != 0:
        warning = "Daemon installed, but it could not be enabled to start on boot."
    if _systemctl("start", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Daemon installed, but the service failed to start."}
    return {"ok": True, "warning": warning}


def uninstall_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    _systemctl("stop", SERVICE_NAME)
    _systemctl("disable", SERVICE_NAME)
    common.sudo_run("rm", "-f", SERVICE_FILE)
    _systemctl("daemon-reload")
    return {"ok": True}


def service_running() -> bool:
    if not is_available():
        return False
    return subprocess.call(
        ["systemctl", "is-active", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def service_enabled() -> bool:
    if not is_available():
        return False
    return subprocess.call(
        ["systemctl", "is-enabled", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def restart_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if _systemctl("restart", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Failed to restart the service."}
    return {"ok": True}


def read_logs(lines: int = 200) -> str:
    if not is_available():
        return "journalctl is not available on this system."
    try:
        out = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager",
             "-o", "short-precise"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Could not read daemon logs: {exc}"
    text = (out.stdout or "").strip()
    if not text:
        return out.stderr.strip() or "No daemon logs yet."
    return text


def service_path_stale() -> bool:
    if not os.path.isfile(SERVICE_FILE):
        return False
    try:
        with open(SERVICE_FILE) as f:
            content = f.read()
    except OSError:
        return False
    current_exec = f"ExecStart={common.python_bin()} {common.daemon_script()}"
    existing_exec = next(
        (line for line in content.splitlines() if line.startswith("ExecStart=")),
        None,
    )
    return existing_exec is not None and existing_exec != current_exec


def regenerate_service() -> dict:
    if not common.sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not common.sudo_write_file(SERVICE_FILE, _render_unit(), ".service"):
        return {"ok": False, "error": "Failed to write the service file."}
    _systemctl("daemon-reload")
    if _systemctl("restart", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Service file updated, but the daemon failed to restart."}
    return {"ok": True}
