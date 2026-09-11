from __future__ import annotations

from pathlib import Path
from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static, Switch

from Assets.core import config as cfg
from Assets.core import platform as plat
from Assets.tui.helpers import exclude_adaptive_when_macos
from Assets.tuning import power


def _privilege_choices() -> list[tuple[str, str]]:
    from Assets.daemon.service import is_sudo_installed, is_run0_installed
    has_sudo = is_sudo_installed()
    has_run0 = is_run0_installed()
    if has_sudo and has_run0:
        auto_label = "Auto-detect (sudo)"
    elif has_sudo:
        auto_label = "Auto-detect (sudo)"
    elif has_run0:
        auto_label = "Auto-detect (run0)"
    else:
        auto_label = "Auto-detect (none)"

    return [
        (auto_label, "auto"),
        ("sudo" if has_sudo else "sudo (not installed)", "sudo"),
        ("run0" if has_run0 else "run0 (not installed)", "run0"),
    ]


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

        with Vertical(classes="settings_card"):
            yield Static("Preferences", classes="card_title")
            with Vertical(classes="setcol"):
                yield Label("Default tab on startup", classes="set_top_label")
                valid = {pid for _, pid in tab_choices}
                current = cfg.get("Settings", "DefaultTab", "home")
                yield Select([(label, pid) for label, pid in tab_choices],
                             value=current if current in valid else "home",
                             allow_blank=False, id="set-default-tab")
            if not plat.IS_MACOS:
                priv_choices = _privilege_choices()
                valid_priv = {pid for _, pid in priv_choices}
                current_priv = cfg.get("Settings", "PrivilegeTool", "auto").lower()
                with Vertical(classes="setcol"):
                    yield Label("Privilege escalation tool", classes="set_top_label")
                    yield Select([(label, pid) for label, pid in priv_choices],
                                 value=current_priv if current_priv in valid_priv else "auto",
                                 allow_blank=False, id="set-privilege-tool")

        with Vertical(classes="settings_card"):
            yield Static("Daemon service", classes="card_title")
            yield Static("", id="daemon_status")
            with Grid(classes="daemon_grid"):
                yield Button("Install / repair", id="daemon_install")
                yield Button("Restart", id="daemon_restart")
                yield Button("View logs", id="daemon_logs")
                yield Button("Uninstall", id="daemon_uninstall", variant="error")

        with Vertical(classes="settings_card"):
            yield Static("Presets backup & restore", classes="card_title")
            with Vertical(classes="setcol"):
                yield Label("Backup export path", classes="set_top_label")
                yield Input(value=str(Path.home() / "zentune_backup.json"), id="backup_filepath")
            with Horizontal(classes="row daemon_buttons", id="backup_buttons"):
                yield Button("Export presets", id="backup_export")
                yield Button("Import presets", id="backup_import")

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
            if cfg.get("Settings", "DefaultTab", "home").lower() != event.value.lower():
                cfg.set_config("Settings", "DefaultTab", event.value)
                cfg.save()
        elif event.control.id == "set-privilege-tool" and isinstance(event.value, str):
            current = cfg.get("Settings", "PrivilegeTool", "auto").lower()
            if current != event.value.lower():
                cfg.set_config("Settings", "PrivilegeTool", event.value)
                cfg.save()
                from Assets.daemon.service import is_sudo_installed, is_run0_installed, get_privilege_tool
                val = event.value.lower()
                if val == "sudo" and not is_sudo_installed():
                    fallback = get_privilege_tool()
                    msg = "sudo is not installed on this system."
                    if fallback != "none":
                        msg += f" Falling back to {fallback}."
                    self.app.notify(msg, title="Privileges", severity="warning")
                elif val == "run0" and not is_run0_installed():
                    fallback = get_privilege_tool()
                    msg = "run0 is not installed on this system."
                    if fallback != "none":
                        msg += f" Falling back to {fallback}."
                    self.app.notify(msg, title="Privileges", severity="warning")
                elif val == "auto":
                    effective = get_privilege_tool()
                    if effective == "none":
                        self.app.notify("Neither sudo nor run0 was found on this system.", title="Privileges", severity="warning")
                    else:
                        self.app.notify(f"Auto-detect will use {effective}.", title="Privileges")
                else:
                    self.app.notify(f"Privilege tool set to {event.value}.", title="Privileges")

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
        elif bid == "backup_export":
            path_val = self.query_one("#backup_filepath", Input).value.strip()
            from Assets.tuning import backup
            ok, msg, _, _ = backup.export_backup(path_val if path_val else None)
            self.app.notify(msg, title="Backup", severity="information" if ok else "error")
        elif bid == "backup_import":
            from Assets.tui.modals import ImportPresetsModal
            self.app.push_screen(ImportPresetsModal())
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
        from Assets.tui.helpers import ensure_sudo, run_privileged_action

        if kind == "uninstall":
            from Assets.tui.modals import ConfirmModal
            if not await self.app.push_screen_wait(ConfirmModal("Uninstall the daemon service?")):
                return

        if not await ensure_sudo(self.app):
            return

        fn = {"install": service.install_service,
              "restart": service.restart_service,
              "uninstall": service.uninstall_service}[kind]
        verb = {"install": "Installing", "restart": "Restarting", "uninstall": "Uninstalling"}[kind]
        self.query_one("#daemon_status", Static).update(f"Service: [yellow]{verb}…[/]")
        result = await run_privileged_action(self.app, fn)
        if kind != "uninstall" and result.get("ok"):
            await asyncio.to_thread(service.wait_for_daemon)
        self._refresh_daemon_status()
        if not result.get("ok"):
            if result.get("cancelled"):
                self.app.notify("Action cancelled.", title="Daemon", severity="warning")
            else:
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
