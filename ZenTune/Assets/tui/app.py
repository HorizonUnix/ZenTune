from __future__ import annotations

import asyncio
import threading
import time

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Static, TabbedContent, TabPane, Footer

from Assets.core import config as cfg
from Assets.core import platform as plat
from Assets.tui import helpers
from Assets.tui.tabs.homeView import HomeTab
from Assets.tui.tabs.premadeView import PowerTab
from Assets.tui.tabs.customView import CustomEditor
from Assets.tui.tabs.adaptiveView import AdaptiveTab
from Assets.tui.tabs.automationsView import AutomationsTab
from Assets.tui.tabs.settingsView import SettingsTab
from Assets.tui.tabs.infoView import HardwareTab
from Assets.tui.tabs.statusView import StatusTab

_PAGES = ["home", "power", "custom", "adaptive", "automations", "hardware", "status", "settings"]


def _available_pages() -> list[str]:
    return helpers.exclude_adaptive_when_macos(_PAGES)


class U4LApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "ZenTune"

    def __init__(self, first_run: bool = False, dep_error: str | None = None) -> None:
        super().__init__()
        self._first_run = first_run
        self._dep_error = dep_error

    BINDINGS = [
        ("h", "show_tab('home')", "Home"),
        ("1", "show_tab('power')", "Premade"),
        ("2", "show_tab('custom')", "Custom"),
        ("3", "show_tab('adaptive')", "Adaptive"),
        ("4", "show_tab('automations')", "Auto"),
        ("5", "show_tab('hardware')", "Info"),
        ("6", "show_tab('status')", "Status"),
        ("7", "show_tab('settings')", "Settings"),
        ("question_mark", "about", "About"),
        ("escape", "focus_tabs", "Tabs"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(helpers.BANNER, id="banner")
        yield Static(helpers.status_line(), id="hwline")
        yield Static("", id="statusline")
        pages = _available_pages()
        initial = cfg.get("Settings", "DefaultTab", "home")
        if initial not in pages:
            initial = "home"
        with TabbedContent(initial=initial, id="tabs"):
            with TabPane("Home", id="home"):
                yield HomeTab()
            with TabPane("Premade", id="power"):
                yield PowerTab()
            with TabPane("Custom", id="custom"):
                yield CustomEditor()
            if "adaptive" in pages:
                with TabPane("Adaptive", id="adaptive"):
                    yield AdaptiveTab()
            with TabPane("Auto", id="automations"):
                yield AutomationsTab()
            with TabPane("Info", id="hardware"):
                yield HardwareTab()
            with TabPane("Status", id="status"):
                yield StatusTab()
            with TabPane("Settings", id="settings"):
                yield SettingsTab()
        yield Static("", id="too_small")
        yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()
        self.set_interval(1.0, self.refresh_status)
        self._start_toast_reaper()
        self.refresh_status()
        self._check_size(self.size)
        if self._dep_error:
            from Assets.tui.modals import FatalErrorModal
            self.push_screen(FatalErrorModal(self._dep_error))
            return
        self._startup_rop_check()
        if self._first_run:
            from Assets.tui.wizard import SetupWizard
            self.push_screen(SetupWizard())
        else:
            self._deferred_startup()

    @work(thread=True, exclusive=True, group="startup")
    def _deferred_startup(self) -> None:
        from Assets.core.hardware import check_ryzen_smu, check_macos_backend
        from Assets.daemon.service import service_path_stale
        from Assets.core.ipc import get_client

        dep_error = check_macos_backend() if plat.IS_MACOS else check_ryzen_smu()
        if not dep_error and cfg.get("Info", "Type") == "Intel":
            dep_error = ("Intel CPUs are not supported.\n\n"
                         "ZenTune only supports AMD Ryzen APUs and desktop CPUs.")

        path_stale = not dep_error and service_path_stale()

        client = get_client()
        st = client.status()
        if not st.get("mode"):
            client.apply_saved()

        daemon_ver = st.get("version", "")
        if daemon_ver and daemon_ver != cfg.LOCAL_VERSION:
            self.call_from_thread(
                self.notify,
                f"TUI is v{cfg.LOCAL_VERSION}, daemon is v{daemon_ver}. Restart the daemon to sync.",
                title="Version mismatch",
                severity="warning",
                timeout=12,
            )

        self.call_from_thread(self._post_startup, dep_error, path_stale)

    def _post_startup(self, dep_error: str | None, path_stale: bool) -> None:
        if dep_error:
            from Assets.tui.modals import FatalErrorModal
            self.push_screen(FatalErrorModal(dep_error))
            return
        if path_stale:
            from Assets.tui.modals import StalePathModal
            self.push_screen(StalePathModal())
        elif cfg.get("Settings", "SoftwareUpdate", "0") == "1":
            self._startup_update_check()

    _theme_subscribed = False

    DEFAULT_THEME = "textual-dark"

    def _apply_theme(self) -> None:
        saved = cfg.get("Settings", "Theme", self.DEFAULT_THEME)
        self.theme = saved if saved in self.available_themes else self.DEFAULT_THEME
        if not self._theme_subscribed:
            self._theme_subscribed = True
            self.theme_changed_signal.subscribe(self, self._save_theme)

    def _save_theme(self, theme) -> None:
        name = getattr(theme, "name", theme)
        if name != cfg.get("Settings", "Theme", ""):
            cfg.set_config("Settings", "Theme", name)
            cfg.save()

    def action_show_tab(self, tab: str) -> None:
        if tab in _available_pages():
            self.query_one("#tabs", TabbedContent).active = tab

    def action_focus_tabs(self) -> None:
        from textual.widgets import Tabs
        try:
            self.set_focus(self.query_one(Tabs))
        except Exception:
            pass

    def action_about(self) -> None:
        from Assets.tui.modals import AboutModal
        self.push_screen(AboutModal())

    def on_resize(self, event) -> None:
        self._check_size(event.size)

    def _check_size(self, size) -> None:
        too_small = size.width < 50 or size.height < 25
        self.query_one("#too_small", Static).display = too_small
        self.query_one("#banner").display = not too_small
        self.query_one("#tabs").display = not too_small
        if too_small:
            self.query_one("#too_small", Static).update("Terminal too small, minimum is 50×25.")
            return
        self.query_one("#banner", Static).update(
            helpers.WORDMARK if size.width < 62 else helpers.BANNER)

    _reaper_stop = False
    _reaper_started = False
    _flush_ticks = 0

    def _start_toast_reaper(self) -> None:
        if self._reaper_started:
            return
        self._reaper_started = True
        loop = asyncio.get_running_loop()

        def _reap() -> None:
            while not self._reaper_stop:
                time.sleep(0.5)
                try:
                    loop.call_soon_threadsafe(self._reap_toasts)
                except RuntimeError:
                    break

        threading.Thread(target=_reap, name="toast-reaper", daemon=True).start()

    def _reap_toasts(self) -> None:
        self._refresh_notifications()
        if len(self._notifications):
            self._flush_ticks = 2
        if self._flush_ticks > 0:
            self._flush_ticks -= 1
            self.refresh()

    def on_unmount(self) -> None:
        self._reaper_stop = True

    _last_status: dict = {"ok": False}

    @work(thread=True, exclusive=True, group="status")
    def refresh_status(self) -> None:
        from Assets.core.ipc import get_client
        st = get_client().status()
        self.call_from_thread(self._render_status, st)

    _warned_offline = False

    def _render_status(self, st: dict) -> None:
        self._last_status = st
        ok = st.get("ok", False)
        from textual.css.query import NoMatches
        try:
            line = self.query_one("#statusline", Static)
        except NoMatches:
            return
        if not ok:
            from Assets.tui.wizard import SetupWizard
            in_setup = isinstance(self.screen, SetupWizard)
            line.display = not in_setup
            line.update("[yellow]Daemon offline. Install or start it from the Settings tab.[/]")
            if not self._warned_offline and not in_setup:
                self._warned_offline = True
                self.notify("Install or start it from the Settings tab.",
                            title="Daemon offline", severity="warning")
            return
        self._warned_offline = False
        line.display = False

    @work(thread=True, exclusive=True, group="startup_rop")
    def _startup_rop_check(self) -> None:
        try:
            from Assets.system import nvcheck
            defective = nvcheck.check_rops()
        except Exception:
            return
        for name, actual, expected in defective:
            self.call_from_thread(self._warn_rop, name, actual, expected)

    def _warn_rop(self, name: str, actual: int, expected: int) -> None:
        self.notify(
            f"ROP count is lower than expected on {name} "
            f"({actual} ROPs out of {expected} ROPs)",
            title="NVIDIA GPU Warning", severity="warning", timeout=10,
        )

    @work(thread=True, exclusive=True, group="startup_update")
    def _startup_update_check(self) -> None:
        from Assets.flows.updater import is_beta_build, beta_available, get_latest_version, _ver_tuple
        try:
            if is_beta_build():
                if beta_available():
                    self.call_from_thread(self._prompt_startup_update, "beta", "")
            else:
                latest = get_latest_version()
                if _ver_tuple(cfg.LOCAL_VERSION) < _ver_tuple(latest):
                    self.call_from_thread(self._prompt_startup_update, "stable", latest)
        except Exception:
            return

    def _prompt_startup_update(self, channel: str, version: str) -> None:
        from Assets.tui.modals import ConfirmModal
        from Assets.tui.modals import UpdateProgressModal
        from Assets.flows.updater import release_url
        if isinstance(self.screen, ConfirmModal):
            return
        if channel == "beta":
            message = ("You are running a beta build.\n\n"
                       "Reinstall the latest beta build? Beta builds are unstable and may "
                       "change without notice.")
        else:
            message = f"A new version is available: {version}\n\nUpdate now?"
        url = release_url(channel)
        self.push_screen(ConfirmModal(message),
                         lambda ok: self.push_screen(UpdateProgressModal(url)) if ok else None)


def run(first_run: bool = False, dep_error: str | None = None):
    return U4LApp(first_run=first_run, dep_error=dep_error).run()
