from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static, Switch

from Assets.core import config as cfg
from Assets.tui.helpers import exclude_adaptive_when_macos
from Assets.tuning import power


_TOGGLES = (
    ("applyonstart", "Apply preset on daemon start", "Settings", "ApplyOnStart"),
    ("autostartadaptive", "Auto start adaptive mode", "Settings", "AutoStartAdaptive"),
    ("softwareupdate", "Software update", "Settings", "SoftwareUpdate"),
    ("debug", "Debug logging", "Settings", "Debug"),
)

_TAB_CHOICES = (
    ("Home", "home"),
    ("Premade Presets", "power"),
    ("Custom Presets", "custom"),
    ("Adaptive Mode", "adaptive"),
    ("Automations", "automations"),
    ("System Info", "hardware"),
    ("Status", "status"),
    ("Settings", "settings"),
)


class SettingsTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        toggles = exclude_adaptive_when_macos(_TOGGLES, key=lambda t: t[0], excluded="autostartadaptive")
        tab_choices = exclude_adaptive_when_macos(_TAB_CHOICES, key=lambda t: t[1])
        with Vertical(classes="settings_card"):
            yield Static("General", classes="card_title")
            for cid, label, section, key in toggles:
                with Horizontal(classes="setrow"):
                    yield Switch(value=cfg.get(section, key, "0") == "1", id=f"set-{cid}")
                    yield Label(label, classes="set_label")
            with Horizontal(classes="setrow"):
                yield Switch(value=cfg.get("Settings", "ReApply", "0") == "1", id="set-reapply")
                yield Label("Reapply preset periodically", classes="set_label")
            with Horizontal(classes="setrow"):
                yield Input(value=cfg.get("Settings", "Time", "3"), type="integer",
                            id="reapply_interval", restrict=r"\d*")
                yield Label("Reapply interval (seconds)", classes="set_label")
            with Horizontal(classes="setrow"):
                valid = {pid for _, pid in tab_choices}
                current = cfg.get("Settings", "DefaultTab", "home")
                yield Select([(label, pid) for label, pid in tab_choices],
                             value=current if current in valid else "home",
                             allow_blank=False, id="set-default-tab")
                yield Label("Default tab on startup", classes="set_label")

        with Vertical(classes="settings_card"):
            yield Static("Daemon service", classes="card_title")
            yield Static("", id="daemon_status")
            with Grid(classes="daemon_grid"):
                yield Button("Install / repair", id="daemon_install")
                yield Button("Restart", id="daemon_restart")
                yield Button("View logs", id="daemon_logs")
                yield Button("Uninstall", id="daemon_uninstall", variant="error")

        with Vertical(classes="settings_card"):
            yield Static("Hardware & reset", classes="card_title")
            with Horizontal(classes="row daemon_buttons"):
                yield Button("Re-detect hardware", id="redetect")
                yield Button("Edit CPU info", id="edit_cpu_info")
                yield Button("Reset all settings", id="reset_all", variant="error")

    def on_mount(self) -> None:
        self._refresh_daemon_status()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        cid = event.control.id.split("-", 1)[1]
        if cid == "reapply":
            cfg.set_config("Settings", "ReApply", "1" if event.value else "0")
            cfg.save()
            self._apply_reapply(event.value)
            return
        _, _, section, key = next(t for t in _TOGGLES if t[0] == cid)
        cfg.set_config(section, key, "1" if event.value else "0")
        cfg.save()
        if cid == "debug":
            self._reload_config()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "reapply_interval":
            return
        if not power.update_reapply_interval(event.value):
            return
        clamped = cfg.get("Settings", "Time", "3")
        event.input.value = clamped
        self.app.notify(f"Reapply interval set to {clamped}s.", title="Reapply")
        if cfg.get("Settings", "ReApply", "0") == "1":
            self._apply_reapply(True)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "set-default-tab" and isinstance(event.value, str):
            cfg.set_config("Settings", "DefaultTab", event.value)
            cfg.save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "redetect":
            self._redetect()
        elif bid == "edit_cpu_info":
            from Assets.tui.modals import CpuInfoModal
            self.app.push_screen(CpuInfoModal())
        elif bid == "reset_all":
            from Assets.tui.modals import ConfirmModal
            self.app.push_screen(
                ConfirmModal("Reset all settings, custom presets and adaptive presets? This cannot be undone."),
                lambda ok: self.app.exit("reset") if ok else None)
        elif bid == "daemon_install":
            from Assets.daemon.service import has_service_manager
            if not has_service_manager():
                from Assets.tui.modals import ManualDaemonModal
                self.app.push_screen(ManualDaemonModal(),
                                     lambda _=None: self._refresh_daemon_status())
            else:
                self._daemon_action("install")
        elif bid == "daemon_restart":
            self._daemon_action("restart")
        elif bid == "daemon_uninstall":
            self._daemon_action("uninstall")
        elif bid == "daemon_logs":
            from Assets.tui.modals import DaemonLogModal
            self.app.push_screen(DaemonLogModal())

    @work(group="settings_daemon")
    async def _daemon_action(self, kind: str) -> None:
        import asyncio
        from Assets.daemon import service
        from Assets.tui.helpers import ensure_sudo

        if kind == "uninstall":
            from Assets.tui.modals import ConfirmModal
            if not await self.app.push_screen_wait(ConfirmModal("Uninstall the daemon service?")):
                return

        if not await ensure_sudo(self.app):
            self.app.notify("Cancelled, administrator access not granted.",
                            title="Daemon", severity="warning")
            return

        fn = {"install": service.install_service,
              "restart": service.restart_service,
              "uninstall": service.uninstall_service}[kind]
        verb = {"install": "Installing", "restart": "Restarting", "uninstall": "Uninstalling"}[kind]
        self.app.notify(f"{verb} daemon…", title="Daemon")
        result = await asyncio.to_thread(fn)
        if kind != "uninstall" and result.get("ok"):
            await asyncio.to_thread(service.wait_for_daemon)
        self._refresh_daemon_status()
        if not result.get("ok"):
            self.app.notify(result.get("error", "Action failed."),
                            title="Daemon", severity="error")
        elif result.get("warning"):
            self.app.notify(result["warning"], title="Daemon", severity="warning")
        else:
            done = {"install": "Daemon installed.", "restart": "Daemon restarted.",
                    "uninstall": "Daemon uninstalled."}[kind]
            self.app.notify(done, title="Daemon")

    @work(group="settings_redetect")
    async def _redetect(self) -> None:
        import asyncio
        from Assets.core.ipc import get_client
        if not get_client().ping():
            self.app.notify("Daemon is not running, cannot detect hardware.",
                            title="Hardware detection", severity="warning")
            return
        from Assets.core.hardware import detect
        await asyncio.to_thread(detect)
        cfg.save()
        from Assets.tui.modals import HardwareInfoModal
        self.app.push_screen(HardwareInfoModal())

    @work(thread=True, exclusive=True, group="settings")
    def _apply_reapply(self, on: bool) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if not client.ping():
            self.app.call_from_thread(self.app.notify, "Daemon is not running.",
                                      title="Reapply", severity="warning")
            return
        if on:
            result = client.apply_saved()
            if not result.get("ok"):
                self.app.call_from_thread(
                    self.app.notify, "Select a preset in the Premade Presets tab first.",
                    title="Reapply", severity="warning")
        else:
            client.stop_loop()

    @work(thread=True, exclusive=True, group="settings_status")
    def _refresh_daemon_status(self) -> None:
        from Assets.daemon.service import service_running, service_enabled, has_service_manager
        if not has_service_manager():
            from Assets.core.ipc import get_client
            if get_client().ping():
                text = "Service: [green]Running[/] ([dim]started manually[/])"
            else:
                text = "Service: [dim]Not running[/] ([dim]no service manager, start manually[/])"
        elif service_running():
            boot = "enabled" if service_enabled() else "disabled"
            text = f"Service: [green]Running[/] ([dim]start on boot: {boot}[/])"
        else:
            text = "Service: [dim]Stopped[/]"
        self.app.call_from_thread(self.query_one("#daemon_status", Static).update, text)

    @work(thread=True, exclusive=True, group="settings")
    def _reload_config(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.reload_config()
