from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import urllib.request

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from Assets.relay import migrate

OLD_ASSETS_DIR = os.path.join(migrate.OLD_SRC_DIR, "Assets")


def _download(url: str, dest_path: str) -> None:
    urllib.request.urlretrieve(url, dest_path)


def _sudo_run(*args: str) -> int:
    return subprocess.run(["sudo", "-n", *args]).returncode


def _sudo_available() -> bool:
    return subprocess.run(
        ["sudo", "-n", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def _prime_sudo(password: str) -> bool:
    return subprocess.run(
        ["sudo", "-S", "-p", "", "-v"], input=password + "\n", text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def _setup_new_install(src_dir: str) -> None:
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from Assets.daemon.service import ensure_venv
    from Assets.daemon.systemd import install_service

    if not ensure_venv():
        raise RuntimeError("Could not set up the ZenTune Python environment.")
    result = install_service()
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Could not install the zentune service."))


def _get_new_client():
    from Assets.core.ipc import get_client
    return get_client()


class _SudoModal(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Administrator access is required to finish migrating to ZenTune.")
            yield Input(password=True, placeholder="Password", id="pw")
            yield Static("", id="error")
            with Horizontal():
                yield Button("Continue", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        pw = self.query_one("#pw", Input).value
        if _prime_sudo(pw):
            self.dismiss(True)
        else:
            self.query_one("#error", Static).update("[red]Incorrect password, try again.[/]")


async def _ensure_sudo(app: App) -> bool:
    if _sudo_available():
        return True
    return bool(await app.push_screen_wait(_SudoModal()))


class RelayApp(App[str]):
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(
                "UXTU4Linux is now ZenTune.\n\n"
                "Your settings and presets will be migrated automatically.",
                id="message",
            )
            yield Static("", id="status")
            with Horizontal():
                yield Button("Continue", id="continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.query_one("#continue", Button).disabled = True
            self._migrate()

    @work
    async def _migrate(self) -> None:
        status = self.query_one("#status", Static)

        if not await _ensure_sudo(self):
            status.update("[red]Administrator access not granted. Aborting.[/]")
            return

        status.update("Stopping the old service…")
        await asyncio.to_thread(migrate.stop_old_daemon, _sudo_run)

        status.update("Reading your existing settings…")
        config_text, presets_text = await asyncio.to_thread(migrate.read_old_state, OLD_ASSETS_DIR)

        status.update("Downloading and installing the current ZenTune release…")
        try:
            await asyncio.to_thread(
                migrate.install_payload,
                migrate.RELEASE_URL, migrate.NEW_INSTALL_DIR, config_text, presets_text,
                _sudo_run, _setup_new_install, _download,
            )
            await asyncio.to_thread(migrate.install_wrapper, migrate.NEW_INSTALL_DIR, _sudo_run)
        except Exception as exc:
            status.update(f"[red]Migration failed: {exc}\nYour old install was not removed.[/]")
            return

        status.update("Starting ZenTune and checking it responds…")
        if not await asyncio.to_thread(migrate.verify_new_daemon, _get_new_client):
            status.update("[red]ZenTune did not start correctly. Your old install was not removed.[/]")
            return

        status.update("Removing the old installation…")
        removed = await asyncio.to_thread(migrate.remove_old_install, _sudo_run)
        if not removed:
            status.update(
                "[yellow]ZenTune is running, but the old install could not be fully "
                f"removed. You can remove {migrate.OLD_INSTALL_DIR} and "
                f"{migrate.OLD_SERVICE_FILE} manually.[/]"
            )
            await asyncio.sleep(3)

        status.update("Done. Launching ZenTune…")
        self.exit("relaunch")


def run_relay() -> None:
    result = RelayApp().run()
    if result == "relaunch":
        new_entry = os.path.join(migrate.NEW_INSTALL_DIR, "src", "zentune.py")
        new_python = os.path.join(migrate.NEW_INSTALL_DIR, "venv", "bin", "python3")
        os.execv(new_python, [new_python, new_entry])
