from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

from Assets.core import config as cfg
from Assets.core import platform as plat


def sudo_available() -> bool:
    return subprocess.run(
        ["sudo", "-n", "-v"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def prime_sudo(password: str) -> bool:
    return subprocess.run(
        ["sudo", "-S", "-p", "", "-v"],
        input=password + "\n", text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def sudo_run(*args: str) -> int:
    return subprocess.run(["sudo", "-n", *args]).returncode


def sudo_write_file(path: str, content: str, suffix: str, owner: str | None = None) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        r = subprocess.run(["sudo", "-n", "mv", tmp, path])
        if r.returncode != 0:
            return False
        if owner is not None:
            sudo_run("chown", owner, path)
            sudo_run("chmod", "644", path)
        return True
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_requirements() -> list[str] | None:
    try:
        with open(cfg.REQUIREMENTS_PATH) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except OSError:
        return None


def ensure_venv() -> bool:
    venv_dir = cfg.VENV_DIR
    venv_python = cfg.VENV_PYTHON

    if not os.path.isfile(venv_python):
        sudo_run("mkdir", "-p", venv_dir)
        if sudo_run(sys.executable, "-m", "venv", "--without-pip", venv_dir) != 0:
            return False
        if sudo_run(venv_python, "-m", "ensurepip", "--upgrade") != 0:
            return False

    reqs = _read_requirements()
    if reqs is None:
        return False
    if not reqs:
        return True
    if sudo_run(venv_python, "-m", "pip", "install", "--upgrade", "--quiet",
                "-r", cfg.REQUIREMENTS_PATH) != 0:
        return False

    return True


def daemon_script() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "daemon.py")


def python_bin() -> str:
    return cfg.VENV_PYTHON if os.path.isfile(cfg.VENV_PYTHON) else sys.executable


def manual_start_command() -> str:
    return f"sudo {python_bin()} {daemon_script()}"


def wait_for_daemon(timeout: float = 10.0, interval: float = 0.3) -> bool:
    from Assets.core.ipc import get_client
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if get_client().ping():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


if plat.IS_MACOS:
    from Assets.daemon import launchd as _backend
else:
    from Assets.daemon import systemd as _backend

has_service_manager = _backend.is_available
install_service = _backend.install_service
uninstall_service = _backend.uninstall_service
service_running = _backend.service_running
service_enabled = _backend.service_enabled
restart_service = _backend.restart_service
read_logs = _backend.read_logs
service_path_stale = _backend.service_path_stale
regenerate_service = _backend.regenerate_service
