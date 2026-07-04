from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from typing import Callable

SudoRun = Callable[..., int]
DownloadFn = Callable[[str, str], None]

OLD_INSTALL_DIR = "/opt/uxtu4linux"
OLD_SRC_DIR = f"{OLD_INSTALL_DIR}/src"
OLD_SERVICE_NAME = "uxtu4linux.service"
OLD_SERVICE_FILE = f"/etc/systemd/system/{OLD_SERVICE_NAME}"
OLD_WRAPPER = "/usr/local/bin/uxtu4linux"

NEW_INSTALL_DIR = "/opt/zentune"
NEW_WRAPPER = "/usr/local/bin/zentune"

RELEASE_URL = "https://github.com/HorizonUnix/ZenTune/releases/latest/download/ZenTune.zip"


def stop_old_daemon(sudo_run: SudoRun) -> None:
    sudo_run("systemctl", "stop", OLD_SERVICE_NAME)
    sudo_run("systemctl", "disable", OLD_SERVICE_NAME)


def read_old_state(old_assets_dir: str) -> tuple[str, str]:
    config_path = os.path.join(old_assets_dir, "config.ini")
    presets_path = os.path.join(old_assets_dir, "custom.json")
    config_text = ""
    presets_text = "[]"
    if os.path.isfile(config_path):
        with open(config_path) as f:
            config_text = f.read()
    if os.path.isfile(presets_path):
        with open(presets_path) as f:
            presets_text = f.read()
    return config_text, presets_text


def install_payload(
    download_url: str,
    install_dir: str,
    config_text: str,
    presets_text: str,
    sudo_run: SudoRun,
    setup_new_install: Callable[[str], None],
    download_fn: DownloadFn,
) -> None:
    src_dir = os.path.join(install_dir, "src")
    sudo_run("mkdir", "-p", install_dir)
    sudo_run("chown", f"{os.getuid()}:{os.getgid()}", install_dir)
    os.makedirs(install_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "ZenTune.zip")
        download_fn(download_url, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        extracted = os.path.join(tmp, "ZenTune")
        if not os.path.isdir(extracted):
            raise RuntimeError("Downloaded release did not contain a ZenTune/ folder.")
        if os.path.exists(src_dir):
            shutil.rmtree(src_dir)
        shutil.copytree(extracted, src_dir)

    assets_dir = os.path.join(src_dir, "Assets")
    with open(os.path.join(assets_dir, "config.ini"), "w") as f:
        f.write(config_text)
    with open(os.path.join(assets_dir, "custom.json"), "w") as f:
        f.write(presets_text)

    setup_new_install(src_dir)


def install_wrapper(install_dir: str, sudo_run: SudoRun) -> None:
    venv_python = os.path.join(install_dir, "venv", "bin", "python3")
    entry = os.path.join(install_dir, "src", "zentune.py")
    script = f'#!/usr/bin/env bash\nexec "{venv_python}" "{entry}" "$@"\n'

    fd, tmp_path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "w") as f:
            f.write(script)
        if sudo_run("cp", tmp_path, NEW_WRAPPER) != 0:
            raise RuntimeError(f"Could not install the {NEW_WRAPPER} launcher.")
        if sudo_run("chmod", "755", NEW_WRAPPER) != 0:
            raise RuntimeError(f"Could not make {NEW_WRAPPER} executable.")
    finally:
        os.remove(tmp_path)


def verify_new_daemon(get_client: Callable[[], object], timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if get_client().ping():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def remove_old_install(sudo_run: SudoRun) -> bool:
    ok = sudo_run("rm", "-rf", OLD_INSTALL_DIR) == 0
    ok = sudo_run("rm", "-f", OLD_WRAPPER) == 0 and ok
    ok = sudo_run("rm", "-f", OLD_SERVICE_FILE) == 0 and ok
    ok = sudo_run("systemctl", "daemon-reload") == 0 and ok
    return ok
