from __future__ import annotations

import os
import subprocess
import tempfile

from Assets.core import config as cfg
from Assets.daemon import service as common

SERVICE_NAME = f"{cfg.APP_NAME}.service"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}"

_available: bool | None = None


def is_available() -> bool:
    global _available
    if _available is None:
        try:
            _available = subprocess.call(
                ["systemctl", "--version"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ) == 0
        except OSError:
            _available = False
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
    return common.privilege_run("systemctl", *args, non_interactive=False)


def install_service() -> dict:
    if not is_available():
        return {"ok": False, "manual": True,
                "error": f"systemctl is not available. Start the daemon manually:\n"
                         f"{common.manual_start_command()}"}
    if common.get_privilege_tool() != "run0" and not common.privilege_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not common.ensure_venv(non_interactive=False):
        return {"ok": False, "error": "Could not prepare the daemon environment."}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
        f.write(_render_unit())
        tmp = f.name
    try:
        cmd = [
            "sh", "-c",
            'install -m 644 -o root -g root "$1" "$2" && '
            'systemctl daemon-reload && '
            'systemctl enable "$3" 2>/dev/null || true; '
            'systemctl restart "$3"',
            "--", tmp, SERVICE_FILE, SERVICE_NAME,
        ]
        ret = common.privilege_run(*cmd, non_interactive=False)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    if ret != 0:
        if common.was_auth_cancelled():
            return {"ok": False, "cancelled": True, "error": "Authorization was cancelled."}
        return {"ok": False, "error": "Daemon installed, but the service failed to start."}
    return {"ok": True}


def uninstall_service() -> dict:
    if not is_available():
        return {"ok": False, "manual": True,
                "error": "systemctl is not available. No service to uninstall."}
    if common.get_privilege_tool() != "run0" and not common.privilege_available():
        return {"ok": False, "error": "Administrator access is required."}
    ret = common.privilege_run(
        "sh", "-c",
        f"systemctl stop {SERVICE_NAME} 2>/dev/null; "
        f"systemctl disable {SERVICE_NAME} 2>/dev/null; "
        f"rm -f {SERVICE_FILE}; "
        f"systemctl daemon-reload 2>/dev/null || true",
        non_interactive=False,
    )
    if ret != 0:
        if common.was_auth_cancelled():
            return {"ok": False, "cancelled": True, "error": "Authorization was cancelled."}
        return {"ok": False, "error": "Failed to uninstall the service."}
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
    if not is_available():
        return {"ok": False, "manual": True,
                "error": f"systemctl is not available. Restart the daemon manually:\n{common.manual_start_command()}"}
    if common.get_privilege_tool() != "run0" and not common.privilege_available():
        return {"ok": False, "error": "Administrator access is required."}
    if _systemctl("restart", SERVICE_NAME) != 0:
        if common.was_auth_cancelled():
            return {"ok": False, "cancelled": True, "error": "Authorization was cancelled."}
        return {"ok": False, "error": "Failed to restart the service."}
    return {"ok": True}


def read_logs(lines: int = 200) -> str:
    if not is_available():
        return (
            "Logs are not available via journalctl on this system (no systemd).\n"
            "View the terminal output where the daemon is running directly."
        )
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
    if not is_available():
        return {"ok": False, "error": "systemctl is not available."}
    if common.get_privilege_tool() != "run0" and not common.privilege_available():
        return {"ok": False, "error": "Administrator access is required."}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
        f.write(_render_unit())
        tmp = f.name
    try:
        cmd = [
            "sh", "-c",
            'install -m 644 -o root -g root "$1" "$2" && '
            'systemctl daemon-reload && '
            'systemctl restart "$3"',
            "--", tmp, SERVICE_FILE, SERVICE_NAME,
        ]
        ret = common.privilege_run(*cmd, non_interactive=False)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    if ret != 0:
        if common.was_auth_cancelled():
            return {"ok": False, "cancelled": True, "error": "Authorization was cancelled."}
        return {"ok": False, "error": "Service file updated, but the daemon failed to restart."}
    return {"ok": True}
