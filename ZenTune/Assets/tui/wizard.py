from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, ContentSwitcher, Static

from Assets.core import config as cfg


TOTAL_STEPS = 3

_DAEMON_INTRO = (
    "ZenTune uses a small background service to talk to your CPU. "
    "It's the only part that needs administrator access, so the app "
    "itself never has to run as root.\n\n"
)


class SetupWizard(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="setup_dialog"):
            yield Static("First-time setup", classes="dialog_title")
            yield Static("", id="setup_progress")
            with ContentSwitcher(initial="welcome", id="setup_switcher"):
                with Vertical(id="welcome"):
                    yield Static("Welcome to ZenTune", classes="setup_step_title")
                    yield Static(
                        "Take control of your AMD Ryzen CPU or APU: tune power limits, "
                        "temperatures, clocks and the Curve Optimiser to fit how you "
                        "actually use your machine, whether that's longer battery life "
                        "or more performance.\n\n"
                        "This is the Linux and macOS port of the Universal x86 Tuning Utility, "
                        "the popular Windows tuning tool.\n\n"
                        "Setup takes about a minute: we'll install a small background "
                        "service and detect your hardware. Let's get started.",
                        classes="setup_body")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Begin setup", id="setup_begin", variant="primary")
                with Vertical(id="daemon"):
                    yield Static("Set up the background service", classes="setup_step_title")
                    yield Static(
                        _DAEMON_INTRO +
                        "Press Install / enable daemon below. You'll be asked for your "
                        "password once, then the service starts automatically and runs on "
                        "every boot.",
                        id="setup_daemon_body", classes="setup_body")
                    yield Static("", id="manual_cmd")
                    yield Static("", id="setup_daemon_status")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Install / enable daemon", id="setup_install", variant="primary")
                        yield Button("Continue", id="setup_daemon_continue", disabled=True)
                with Vertical(id="hardware"):
                    yield Static("Detect your hardware", classes="setup_step_title")
                    yield Static(
                        "Last step. We're identifying your processor so the right presets "
                        "and tuning options load for your exact chip.\n\n"
                        "This runs automatically, just a moment. When it's done, press "
                        "Finish.",
                        classes="setup_body")
                    yield Static("", id="setup_hw_result")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Detect again", id="setup_detect")
                        yield Button("Finish", id="setup_finish", disabled=True, variant="success")

    def on_mount(self) -> None:
        self._manual = False
        self.query_one("#manual_cmd", Static).display = False
        self._set_step(1)

    def _set_step(self, n: int) -> None:
        dots = "  ".join("[#2f81f7]●[/]" if i <= n else "[dim]○[/]" for i in range(1, TOTAL_STEPS + 1))
        self.query_one("#setup_progress", Static).update(f"{dots}    [dim]Step {n} of {TOTAL_STEPS}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "setup_begin":
            self.query_one(ContentSwitcher).current = "daemon"
            self._set_step(2)
            self._enter_daemon_step()
        elif bid == "setup_install":
            if self._manual:
                self.query_one("#setup_daemon_status", Static).update("Checking…")
                self._refresh_daemon()
            else:
                self._install_daemon()
        elif bid == "setup_daemon_continue":
            self.query_one(ContentSwitcher).current = "hardware"
            self._set_step(3)
            self.query_one("#setup_hw_result", Static).update("Detecting hardware…")
            self._detect()
        elif bid == "setup_detect":
            self.query_one("#setup_hw_result", Static).update("Detecting hardware…")
            self._detect()
        elif bid == "setup_finish":
            cfg.save()
            self.app.exit("setup-done")

    def _enter_daemon_step(self) -> None:
        from Assets.daemon.service import has_service_manager, manual_start_command
        self._manual = not has_service_manager()
        cmd = self.query_one("#manual_cmd", Static)
        if self._manual:
            self.query_one("#setup_daemon_body", Static).update(
                _DAEMON_INTRO +
                "No supported service manager (systemd or launchd) was found on "
                "this system, so the service can't be installed automatically. "
                "Start the daemon yourself in a terminal with administrator access:")
            cmd.update(manual_start_command())
            cmd.display = True
            self.query_one("#setup_install", Button).label = "Check connection"
        else:
            cmd.display = False
            self.query_one("#setup_install", Button).label = "Install / enable daemon"
        self._refresh_daemon()

    @work(group="setup_install")
    async def _install_daemon(self) -> None:
        import asyncio
        from Assets.daemon import service
        from Assets.tui.helpers import ensure_sudo

        if not await ensure_sudo(self.app):
            self.query_one("#setup_daemon_status", Static).update(
                "[yellow]Administrator access not granted.[/]")
            return
        self.query_one("#setup_install", Button).disabled = True
        self.query_one("#setup_daemon_status", Static).update("Installing daemon…")
        result = await asyncio.to_thread(service.install_service)
        if result.get("ok"):
            await asyncio.to_thread(service.wait_for_daemon)
        self.query_one("#setup_install", Button).disabled = False
        if not result.get("ok"):
            self.query_one("#setup_daemon_status", Static).update(
                f"[red]{result.get('error', 'Installation failed.')}[/]")
            return
        self._refresh_daemon()

    @work(thread=True, exclusive=True, group="setup")
    def _refresh_daemon(self) -> None:
        from Assets.core.ipc import get_client
        running = get_client().ping()
        self.app.call_from_thread(self._render_daemon, running)

    def _render_daemon(self, running: bool) -> None:
        if running:
            self.query_one("#setup_daemon_status", Static).update("Daemon: [green]running[/]")
        else:
            self.query_one("#setup_daemon_status", Static).update("Daemon: [yellow]not running[/]")
        self.query_one("#setup_daemon_continue", Button).disabled = not running

    @work(thread=True, exclusive=True, group="setup")
    def _detect(self) -> None:
        from Assets.core.hardware import detect
        try:
            detect()
            cfg.save()
            err = None
        except Exception as exc:
            err = str(exc)
        self.app.call_from_thread(self._render_hardware, err)

    def _render_hardware(self, err: str | None) -> None:
        result = self.query_one("#setup_hw_result", Static)
        if err:
            result.update(f"[red]Detection failed:[/] {err}")
            return
        from Assets.tui.helpers import hardware_info_lines
        result.update("\n".join(hardware_info_lines()))
        self.query_one("#setup_finish", Button).disabled = False
