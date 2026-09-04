from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

from Assets.core import config as cfg
from Assets.core import platform as plat


def get_privilege_tool() -> str:
    if plat.IS_MACOS:
        return "sudo"
    configured = cfg.get("Settings", "PrivilegeTool", "auto").strip().lower()
    if configured == "run0":
        if shutil.which("run0") or os.path.isfile("/usr/bin/run0"):
            return "run0"
    elif configured == "sudo":
        if shutil.which("sudo") or os.path.isfile("/usr/bin/sudo"):
            return "sudo"
    if shutil.which("sudo") or os.path.isfile("/usr/bin/sudo"):
        return "sudo"
    if shutil.which("run0") or os.path.isfile("/usr/bin/run0"):
        return "run0"
    return "sudo"


def privilege_available() -> bool:
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    tool = get_privilege_tool()
    if tool == "run0":
        try:
            return subprocess.run(
                ["run0", "--no-ask-password", "true"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        return subprocess.run(
            ["sudo", "-n", "-v"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def sudo_available() -> bool:
    return privilege_available()


def prime_privilege(password: str = "") -> bool:
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    tool = get_privilege_tool()
    if tool == "run0":
        try:
            return subprocess.run(["run0", "true"]).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    if password:
        try:
            return subprocess.run(
                ["sudo", "-S", "-p", "", "-v"],
                input=password + "\n", text=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    else:
        try:
            return subprocess.run(
                ["sudo", "-v"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False


def prime_sudo(password: str) -> bool:
    return prime_privilege(password)


def privilege_run(*args: str, non_interactive: bool = True) -> int:
    try:
        if os.geteuid() == 0:
            return subprocess.run(list(args)).returncode
    except AttributeError:
        pass
    tool = get_privilege_tool()
    if tool == "run0":
        cmd = ["run0"]
        if non_interactive:
            cmd.append("--no-ask-password")
        cmd.extend(args)
        try:
            return subprocess.run(cmd).returncode
        except (OSError, subprocess.SubprocessError):
            return 1
    cmd = ["sudo"]
    if non_interactive:
        cmd.append("-n")
    cmd.extend(args)
    try:
        return subprocess.run(cmd).returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def sudo_run(*args: str) -> int:
    return privilege_run(*args)


def privilege_write_file(path: str, content: str, suffix: str, owner: str | None = None, mode: str = "644") -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        try:
            if os.geteuid() == 0:
                shutil.copy2(tmp, path)
                os.chmod(path, int(mode, 8))
                return True
        except AttributeError:
            pass

        cmd = ["install", "-m", mode]
        if owner is not None:
            parts = owner.split(":")
            cmd.extend(["-o", parts[0]])
            if len(parts) > 1:
                cmd.extend(["-g", parts[1]])
        cmd.extend([tmp, path])

        if privilege_run(*cmd) == 0:
            return True

        if privilege_run("cp", tmp, path) != 0:
            return False
        privilege_run("chmod", mode, path)
        if owner is not None:
            privilege_run("chown", owner, path)
        return True
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def sudo_write_file(path: str, content: str, suffix: str, owner: str | None = None) -> bool:
    return privilege_write_file(path, content, suffix, owner=owner)


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
        privilege_run("mkdir", "-p", venv_dir)
        if privilege_run(sys.executable, "-m", "venv", "--without-pip", venv_dir) != 0:
            return False
        if privilege_run(venv_python, "-m", "ensurepip", "--upgrade") != 0:
            return False

    reqs = _read_requirements()
    if reqs is None:
        return False
    if not reqs:
        return True

    all_installed = True
    for req in reqs:
        pkg = req.split("<")[0].split(">")[0].split("=")[0].split("!")[0].strip()
        mod = {"pyzmq": "zmq", "textual-plotext": "textual_plotext"}.get(pkg, pkg)
        if subprocess.run([venv_python, "-c", f"import {mod}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            all_installed = False
            break

    if not all_installed:
        if privilege_run(venv_python, "-m", "pip", "install", "--upgrade", "--quiet",
                         "-r", cfg.REQUIREMENTS_PATH) != 0:
            return False

    return True


def daemon_script() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "daemon.py")


def python_bin() -> str:
    return cfg.VENV_PYTHON if os.path.isfile(cfg.VENV_PYTHON) else sys.executable


def manual_start_command() -> str:
    tool = get_privilege_tool()
    return f"{tool} {python_bin()} {daemon_script()}"


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
