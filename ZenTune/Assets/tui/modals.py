from __future__ import annotations

import re
import webbrowser

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, RichLog, Static

from Assets.core import config as cfg


class FatalErrorModal(ModalScreen):
    def __init__(self, message: str) -> None:
        super().__init__()
        self._guide_url: str | None = None
        match = re.search(r"Install guide:\s*(\S+)", message)
        if match:
            self._guide_url = match.group(1)
            message = message[: match.start()].rstrip()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="fatal_dialog"):
            yield Label("Cannot start ZenTune", classes="dialog_title")
            yield Static(self._message, id="fatal_message")
            if self._guide_url:
                yield Static(
                    f"Install guide: [link='{self._guide_url}']{self._guide_url}[/link]",
                    id="fatal_guide_link")
            with Horizontal(id="dialog_buttons"):
                if self._guide_url:
                    yield Button("Install guide", id="fatal_guide", variant="primary")
                yield Button("Exit", id="fatal_exit", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fatal_guide" and self._guide_url:
            webbrowser.open(self._guide_url)
            return
        self.app.exit()


class DaemonLogModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="log_dialog"):
            yield Label("Daemon logs", classes="dialog_title")
            yield RichLog(id="log_view", wrap=False, highlight=False, markup=False,
                          auto_scroll=False)
            with Horizontal(id="dialog_buttons"):
                yield Button("Close", id="log_close", variant="primary")

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.5, self._refresh)

    @work(thread=True, exclusive=True, group="daemon_log_modal")
    def _refresh(self) -> None:
        from Assets.daemon.service import read_logs
        text = read_logs(200)
        self.app.call_from_thread(self._render_log, text)

    def _render_log(self, text: str) -> None:
        view = self.query_one("#log_view", RichLog)
        was_at_bottom = view.scroll_offset.y >= view.max_scroll_y
        prev_y = view.scroll_offset.y
        view.clear()
        view.write(text)
        self.call_after_refresh(self._restore_scroll, was_at_bottom, prev_y)

    def _restore_scroll(self, was_at_bottom: bool, prev_y: int) -> None:
        view = self.query_one("#log_view", RichLog)
        if was_at_bottom:
            view.scroll_end(animate=False)
        else:
            view.scroll_to(y=prev_y, animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class HardwareInfoModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        from Assets.tui.helpers import hardware_info_lines
        with Vertical(id="hw_dialog"):
            yield Label("Detected hardware", classes="dialog_title")
            yield Static("\n".join(hardware_info_lines()), id="hw_info")
            with Horizontal(id="hw_buttons"):
                yield Button("Close", id="hw_close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class CpuInfoModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Edit CPU info", classes="dialog_title")
            yield Static(
                "Overrides the CPU name used to pick a premade preset. Doesn't touch "
                "your real detected Architecture/Family/Type.",
                id="cpuinfo_help",
            )
            yield Input(value=cfg.get("Info", "CPU"), placeholder="CPU name", id="cpuinfo_name")
            yield Static("", id="cpuinfo_result")
            with Horizontal(id="dialog_buttons"):
                yield Button("Save", id="cpuinfo_save", variant="primary")
                yield Button("Cancel", id="cpuinfo_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cpuinfo_cancel":
            self.dismiss()
            return
        name = self.query_one("#cpuinfo_name", Input).value.strip()
        result = self.query_one("#cpuinfo_result", Static)
        if not name:
            result.update("[red]CPU name is required.[/]")
            return
        cfg.set_config("Info", "CPU", name)
        cfg.save()
        self._reload_and_close()

    @work(thread=True)
    def _reload_and_close(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.reload_config()
        self.app.call_from_thread(self.app.notify, "CPU info saved.", title="Saved")
        self.app.call_from_thread(self.dismiss)

    def action_close(self) -> None:
        self.dismiss()


class StalePathModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Daemon service out of date", classes="dialog_title")
            yield Static("ZenTune was moved since the daemon service was installed, so "
                         "its service file points to the old location.\n\nUpdating it now…",
                         id="stale_msg")
            with Horizontal(id="dialog_buttons"):
                yield Button("Close", id="stale_close", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self._fix()

    @work
    async def _fix(self) -> None:
        import asyncio
        from Assets.tui.helpers import ensure_sudo
        from Assets.daemon import service

        msg = self.query_one("#stale_msg", Static)
        close = self.query_one("#stale_close", Button)
        if not await ensure_sudo(self.app):
            msg.update("ZenTune was moved since the daemon was installed, so its service "
                       "file points to the old location.\n\n[yellow]Administrator access was "
                       "not granted, so it was not updated. Reinstall the daemon from the "
                       "Settings tab.[/]")
            close.disabled = False
            return
        result = await asyncio.to_thread(service.regenerate_service)
        if result.get("ok"):
            msg.update("ZenTune was moved since the daemon was installed.\n\n[green]Its "
                       "service file has been updated and the daemon restarted.[/]")
        else:
            msg.update("The daemon's service file is out of date.\n\n"
                       f"[red]{result.get('error', 'Could not update it.')}[/]")
        close.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class ManualDaemonModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        from Assets.daemon.service import manual_start_command
        with Vertical(id="dialog"):
            yield Label("Start the daemon manually", classes="dialog_title")
            yield Static(
                "No supported service manager (systemd or launchd) was found on "
                "this system, so ZenTune can't install the daemon as a "
                "background service. You can still use everything, you just "
                "need to start the daemon yourself in a terminal with "
                "administrator access:",
                id="manual_msg")
            yield Static(manual_start_command(), id="manual_cmd")
            yield Static(
                "Leave that terminal open, then press Check connection. To start it "
                "automatically on boot, add the command to your init system.",
                id="manual_hint")
            yield Static("", id="manual_status")
            with Horizontal(id="dialog_buttons"):
                yield Button("Check connection", id="manual_check", variant="primary")
                yield Button("Close", id="manual_close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "manual_close":
            self.dismiss()
        else:
            self.query_one("#manual_status", Static).update("Checking…")
            self._check()

    @work(thread=True, exclusive=True)
    def _check(self) -> None:
        from Assets.core.ipc import get_client
        running = get_client().ping()
        self.app.call_from_thread(self._render_result, running)

    def _render_result(self, running: bool) -> None:
        if running:
            self.query_one("#manual_status", Static).update(
                "[green]Connected, the daemon is running.[/]")
        else:
            self.query_one("#manual_status", Static).update(
                "[yellow]Not reachable yet. Make sure the command above is still running.[/]")

    def action_close(self) -> None:
        self.dismiss()


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._prompt, id="confirm_prompt")
            with Horizontal(id="dialog_buttons"):
                yield Button("Yes", variant="error", id="yes", classes="confirm_btn")
                yield Button("No", id="no", classes="confirm_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class AboutModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="about_dialog"):
            yield Label("About ZenTune", classes="dialog_title")
            yield Static(
                f"Version     [b]v{cfg.LOCAL_VERSION}[/]\n"
                f"Build       {cfg.LOCAL_BUILD}\n\n"
                "Maintainer  oxGorou\n"
                "Advisor     NotchApple1703", id="about_info")
            with Horizontal(id="about_buttons"):
                yield Button("GitHub", id="about_github", classes="about_btn github_btn")
                yield Button("Check updates", id="about_update",
                             variant="primary", classes="about_btn")
                yield Button("Close", id="about_close", classes="about_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "about_github":
            webbrowser.open("https://github.com/HorizonUnix/ZenTune")
        elif event.button.id == "about_update":
            self.app.push_screen(UpdaterModal())
        else:
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class UpdaterModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="updater_dialog"):
            yield Label("Software Update", classes="dialog_title")
            yield Static(f"Current version: v{cfg.LOCAL_VERSION}")
            yield Static("Checking for updates…", id="upd_status")
            with VerticalScroll(id="upd_changelog_scroll"):
                yield Markdown("", id="upd_changelog")
            with Horizontal(id="upd_buttons"):
                yield Button("Update now", id="upd_do", variant="success", disabled=True)
                yield Button("Install Beta", id="upd_beta", variant="warning")
                yield Button("Close", id="upd_close", variant="primary")

    def on_mount(self) -> None:
        self._check()

    @work(thread=True, exclusive=True, group="updater")
    def _check(self) -> None:
        from Assets.flows.updater import get_latest_version, get_changelog, beta_available
        try:
            latest = get_latest_version()
            changelog = get_changelog()
        except Exception as exc:
            self.app.call_from_thread(
                self.query_one("#upd_status", Static).update, f"Could not check for updates: {exc}")
            return
        self.app.call_from_thread(self._show, latest, changelog, beta_available())

    def _show(self, latest: str, changelog: str, beta_ok: bool = True) -> None:
        from Assets.flows.updater import _ver_tuple
        up_to_date = _ver_tuple(cfg.LOCAL_VERSION) >= _ver_tuple(latest)
        self.query_one("#upd_status", Static).update(
            "You are on the latest version." if up_to_date else f"Update available: {latest}")
        self.query_one("#upd_changelog", Markdown).update(changelog)
        btn = self.query_one("#upd_do", Button)
        btn.label = "Reinstall" if up_to_date else "Update now"
        btn.disabled = False
        beta_btn = self.query_one("#upd_beta", Button)
        if not beta_ok:
            beta_btn.disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from Assets.flows.updater import release_url
        if event.button.id == "upd_do":
            self.app.push_screen(UpdateProgressModal(release_url("stable")))
        elif event.button.id == "upd_beta":
            self.app.push_screen(
                ConfirmModal("Switch to the beta build? Beta builds are unstable and may be broken."),
                lambda ok: self.app.push_screen(UpdateProgressModal(release_url("beta"))) if ok else None)
        else:
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class UpdateProgressModal(ModalScreen):
    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Updating ZenTune", classes="dialog_title")
            yield Static("Preparing…", id="update_status")
            with Horizontal(id="dialog_buttons"):
                yield Button("Close", id="update_close", disabled=True)

    def on_mount(self) -> None:
        self._run()

    @work
    async def _run(self) -> None:
        import asyncio
        from Assets.tui.helpers import ensure_sudo
        from Assets.flows.updater import perform_update

        status = self.query_one("#update_status", Static)
        if not await ensure_sudo(self.app):
            status.update("[yellow]Administrator access not granted.[/]")
            self.query_one("#update_close", Button).disabled = False
            return

        def report(msg: str) -> None:
            self.app.call_from_thread(status.update, msg)

        result = await asyncio.to_thread(perform_update, self._url, report)
        if result.get("ok"):
            self.app.exit("relaunch")
        else:
            status.update(f"[red]Update failed:[/] {result.get('error', 'unknown error')}")
            self.query_one("#update_close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class SudoModal(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="sudo_dialog"):
            yield Static("Administrator access required", classes="dialog_title")
            yield Static(
                "Enter your password to install or manage the system daemon.",
                id="sudo_desc")
            yield Input(password=True, placeholder="Password", id="sudo_pw")
            yield Static("", id="sudo_error")
            with Horizontal(id="sudo_buttons"):
                yield Button("Authenticate", id="sudo_ok", variant="primary")
                yield Button("Cancel", id="sudo_cancel")

    def on_mount(self) -> None:
        self.query_one("#sudo_pw", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sudo_cancel":
            self.dismiss(False)
        elif event.button.id == "sudo_ok":
            self._submit()

    def _submit(self) -> None:
        pw = self.query_one("#sudo_pw", Input).value
        if not pw:
            self.query_one("#sudo_error", Static).update("[red]Enter a password.[/]")
            return
        self.query_one("#sudo_error", Static).update("Authenticating…")
        self.query_one("#sudo_ok", Button).disabled = True
        self._authenticate(pw)

    @work(thread=True, exclusive=True, group="sudo")
    def _authenticate(self, password: str) -> None:
        from Assets.daemon.service import prime_sudo
        ok = prime_sudo(password)
        self.app.call_from_thread(self._result, ok)

    def _result(self, ok: bool) -> None:
        if ok:
            self.dismiss(True)
            return
        self.query_one("#sudo_error", Static).update("[red]Incorrect password, try again.[/]")
        pw = self.query_one("#sudo_pw", Input)
        pw.value = ""
        pw.focus()
        self.query_one("#sudo_ok", Button).disabled = False
