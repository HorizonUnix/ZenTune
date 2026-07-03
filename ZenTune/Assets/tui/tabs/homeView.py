from __future__ import annotations

import math

from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
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

    @property
    def _nav(self):
        from Assets.tui.helpers import exclude_adaptive_when_macos
        return exclude_adaptive_when_macos(self._NAV_BASE, key=lambda t: t[1])

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

    def compose(self) -> ComposeResult:
        from Assets.core import hardware as hw
        from Assets.system import sensors
        self._caps = sensors.capabilities()
        self._series = {}
        self._ranges = {key: rng for key, _t, _u, rng in self._GRAPHS}
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
            with Grid(classes="graph_grid"):
                for key, title, _unit, _rng in active:
                    self._series[key] = []
                    with Vertical(classes="settings_card graph_card"):
                        yield Static(title, classes="card_title")
                        yield Static("", id=f"graph_value_{key}", classes="graph_value")
                        yield Static("", id=f"graph_minmax_{key}", classes="graph_minmax")
                        yield PlotextPlot(id=f"graph_{key}")
        with Vertical(classes="settings_card"):
            yield Static("Go to", classes="card_title")
            with Grid(classes="home_grid"):
                for label, tab in self._nav:
                    yield Button(label, id=f"home-{tab}", variant="primary")

    def on_mount(self) -> None:
        self._run_poll()
        self.set_interval(1.0, self._run_poll)

    @work(thread=True, exclusive=True, group="home_sensors")
    def _run_poll(self) -> None:
        from Assets.system import sensors
        snapshot = sensors.sample()
        self.app.call_from_thread(self._render_snapshot, snapshot)

    def _render_snapshot(self, snapshot) -> None:
        for key, title, unit, _rng in self._GRAPHS:
            if key not in self._series:
                continue
            rng = self._ranges.get(key)
            value = getattr(snapshot, key)
            if value is None:
                continue
            series = self._series[key]
            series.append(float(value))
            del series[:-self._WINDOW]
            if unit == "%":
                lo = rng[0] if rng is not None else 0
                hi = rng[1] if rng is not None else 100
                floor = lo + (hi - lo) * 0.1
                plot_data = [max(v, floor) for v in series]
            else:
                plot_data = series
            plot = self.query_one(f"#graph_{key}", PlotextPlot)
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
            self.query_one(f"#graph_value_{key}", Static).update(
                f"[b]{round(value)}[/]{unit_sfx}")
            self.query_one(f"#graph_minmax_{key}", Static).update(
                f"Min {round(min(series))}{mm_sfx} • Max {round(max(series))}{mm_sfx}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("home-"):
            self.app.set_focus(None)
            self.app.action_show_tab(bid[len("home-"):])
