from __future__ import annotations

import math

from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Static
from textual_plotext import PlotextPlot

from Assets.core import config as cfg
from Assets.core import platform as plat


class HomeTab(VerticalScroll):
    _NAV_BASE = (
        ("Premade Presets", "power"),
        ("Custom Presets", "custom"),
        ("Adaptive Mode", "adaptive"),
        ("Automations", "automations"),
        ("Info", "hardware"),
        ("Status", "status"),
        ("Settings", "settings"),
    )

    _LINUX_NAV_KEYS = ("power", "custom", "adaptive", "automations")

    @property
    def _nav(self):
        if plat.IS_MACOS:
            from Assets.tui.helpers import exclude_adaptive_when_macos
            return exclude_adaptive_when_macos(self._NAV_BASE, key=lambda t: t[1])
        return tuple(t for t in self._NAV_BASE if t[1] in self._LINUX_NAV_KEYS)

    _GRAPHS = (
        ("cpu_temp", "CPU Temperature", "°C", (-10, 110)),
        ("cpu_power", "CPU Power", "W", None),
        ("cpu_clk", "CPU Clock", "MHz", None),
        ("cpu_load", "CPU Usage", "%", (0, 100)),
        ("igpu_clk", "iGPU Clock", "MHz", None),
        ("igpu_load", "iGPU Usage", "%", (0, 100)),
    )

    _IGPU_KEYS = {"igpu_clk", "igpu_load"}

    _WINDOW = 30
    _PM_KEYS = ("cpu_temp", "cpu_load", "cpu_power", "igpu_clk")

    def _defer_telemetry(self) -> bool:
        try:
            app = self.app
        except Exception:
            return False
        return bool(getattr(app, "_first_run", False) or getattr(app, "_dep_error", None))

    def _make_graph_card(self, key: str, title: str) -> Vertical:
        return Vertical(
            Static(title, classes="card_title"),
            Static("", id=f"graph_value_{key}", classes="graph_value"),
            Static("", id=f"graph_minmax_{key}", classes="graph_minmax"),
            PlotextPlot(id=f"graph_{key}"),
            id=f"graph_card_{key}",
            classes="settings_card graph_card",
        )

    def compose(self) -> ComposeResult:
        from Assets.core import hardware as hw
        from Assets.system import sensors
        self._series = {}
        self._pending_daemon_graphs = set()
        self._daemon_pm_unsupported = False
        self._daemon_pm_unreachable = False
        self._daemon_pm_version = ""
        self._ranges = {key: rng for key, _t, _u, rng in self._GRAPHS}
        if self._defer_telemetry():
            self._caps = set()
            active = []
        else:
            self._caps = sensors.capabilities()
            max_clock = hw.max_clock_mhz()
            if max_clock and max_clock > 0:
                self._ranges["cpu_clk"] = (0, max_clock)
            igpu_max = sensors.igpu_max_clock()
            if igpu_max and igpu_max > 0:
                self._ranges["igpu_clk"] = (0, int(igpu_max))
            is_apu = cfg.get("Info", "Type") == "Amd_Apu"
            if plat.IS_MACOS:
                active = []
            else:
                active = [
                    g for g in self._GRAPHS
                    if g[0] in self._caps and (g[0] not in self._IGPU_KEYS or is_apu)
                ]
        if active:
            with Grid(classes="graph_grid", id="home_graph_grid"):
                for key, title, _unit, _rng in active:
                    self._series[key] = []
                    yield self._make_graph_card(key, title)
        with Vertical(classes="settings_card", id="home_nav_card"):
            yield Static("Go to", classes="card_title")
            with Grid(classes="home_grid"):
                for label, tab in self._nav:
                    yield Button(label, id=f"home-{tab}", variant="primary")

    def on_mount(self) -> None:
        if self._defer_telemetry():
            return
        self._run_poll()
        self.set_interval(1.0, self._run_poll)

    def _supplement_from_daemon(self, snapshot) -> tuple[object, set[str]]:
        from Assets.system import sensors
        if plat.IS_MACOS or sensors.pm_available() is not False:
            return snapshot, set()
        is_apu = cfg.get("Info", "Type") == "Amd_Apu"
        needs_pm = (
            snapshot.cpu_temp is None
            or snapshot.cpu_load is None
            or snapshot.cpu_power is None
            or (is_apu and snapshot.igpu_clk is None)
        )
        if not needs_pm:
            return snapshot, set()

        st = getattr(self.app, "_last_status", {})
        if st.get("ok"):
            self._daemon_pm_unreachable = False
            ver = st.get("version", "")
            if ver != self._daemon_pm_version:
                self._daemon_pm_unsupported = False
                self._daemon_pm_version = ver
            if not st.get("backend"):
                return snapshot, set()
        if self._daemon_pm_unreachable or self._daemon_pm_unsupported:
            return snapshot, set()

        from Assets.core.ipc import get_client
        resp = get_client().pm_sensors()
        if not resp.get("ok"):
            if "unknown command" in resp.get("error", ""):
                self._daemon_pm_unsupported = True
            else:
                self._daemon_pm_unreachable = True
            return snapshot, set()

        pm = resp.get("pm")
        if not isinstance(pm, dict):
            return snapshot, set()

        before = {k: getattr(snapshot, k) for k in self._PM_KEYS}
        merged = sensors.merge_pm(snapshot, pm)
        added = {k for k, prev in before.items() if prev is None and getattr(merged, k) is not None}
        return merged, added

    @work(thread=True, exclusive=True, group="home_sensors")
    def _run_poll(self) -> None:
        from Assets.system import sensors
        snapshot = sensors.sample()
        snapshot, daemon_pm_keys = self._supplement_from_daemon(snapshot)
        self.app.call_from_thread(self._render_snapshot, snapshot, daemon_pm_keys)

    def _update_graph(self, key: str, unit: str, value: float) -> None:
        if not math.isfinite(value):
            return
        try:
            plot = self.query_one(f"#graph_{key}", PlotextPlot)
            val_widget = self.query_one(f"#graph_value_{key}", Static)
            mm_widget = self.query_one(f"#graph_minmax_{key}", Static)
        except NoMatches:
            return
        rng = self._ranges.get(key)
        series = self._series[key]
        series.append(value)
        del series[:-self._WINDOW]
        if unit == "%":
            lo = rng[0] if rng is not None else 0
            hi = rng[1] if rng is not None else 100
            floor = lo + (hi - lo) * 0.1
            plot_data = [max(v, floor) for v in series]
        else:
            plot_data = series
        plot.plt.clear_data()
        plot.plt.plot(plot_data, marker="braille", color="cyan")
        plot.plt.frame(False)
        plot.plt.xticks([])
        plot.plt.yticks([])
        if rng is not None:
            plot.plt.ylim(rng[0], rng[1])
        else:
            hi_v = max(series)
            ceiling = math.ceil(hi_v / 50) * 50 if hi_v > 0 else 50
            plot.plt.ylim(-10, ceiling)
        plot.refresh()
        unit_sfx = f" [dim]{unit}[/]" if unit else ""
        mm_sfx = f" {unit}" if unit else ""
        val_widget.update(f"[b]{round(value)}[/]{unit_sfx}")
        mm_widget.update(f"Min {round(min(series))}{mm_sfx} • Max {round(max(series))}{mm_sfx}")

    async def _mount_daemon_graphs(self, to_add: list[tuple[str, str]], snapshot) -> None:
        try:
            if not self.is_mounted:
                return
            try:
                grid = self.query_one("#home_graph_grid", Grid)
            except NoMatches:
                try:
                    nav_card = self.query_one("#home_nav_card")
                except NoMatches:
                    return
                grid = Grid(classes="graph_grid", id="home_graph_grid")
                await self.mount(grid, before=nav_card)

            order = [k for k, *_ in self._GRAPHS]
            units = {k: u for k, _t, u, _r in self._GRAPHS}
            for key, title in to_add:
                if not self.is_mounted or key in self._series:
                    continue
                before_widget = None
                idx = order.index(key)
                for later_key in order[idx + 1:]:
                    try:
                        before_widget = grid.query_one(f"#graph_card_{later_key}")
                        break
                    except NoMatches:
                        continue
                await grid.mount(self._make_graph_card(key, title), before=before_widget)
                self._series[key] = []
                self._caps.add(key)
                val = getattr(snapshot, key)
                if val is not None:
                    self._update_graph(key, units[key], float(val))
        finally:
            for key, _ in to_add:
                self._pending_daemon_graphs.discard(key)

    def _render_snapshot(self, snapshot, daemon_pm_keys: set[str] | None = None) -> None:
        if not self.is_mounted:
            return
        for key, _title, unit, _rng in self._GRAPHS:
            if key not in self._series:
                continue
            value = getattr(snapshot, key)
            if value is None:
                continue
            self._update_graph(key, unit, float(value))

        if not plat.IS_MACOS and daemon_pm_keys:
            is_apu = cfg.get("Info", "Type") == "Amd_Apu"
            to_add = [
                (k, title)
                for k, title, _unit, _rng in self._GRAPHS
                if (
                    k in daemon_pm_keys
                    and k not in self._series
                    and k not in self._pending_daemon_graphs
                    and (k not in self._IGPU_KEYS or is_apu)
                )
            ]
            if to_add:
                for k, _ in to_add:
                    self._pending_daemon_graphs.add(k)
                self.run_worker(self._mount_daemon_graphs(to_add, snapshot), group="home_mount")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("home-"):
            self.app.set_focus(None)
            self.app.action_show_tab(bid[len("home-"):])
