from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Select, Static, Switch

from Assets.core import config as cfg


class AdaptiveTab(VerticalScroll):
    _FIELDS = (
        ("max_temp", "Max Temperature Limit", "°C", 85),
        ("power", "Max Power Limit", "W", 28),
        ("co_max", "Max Curve Optimiser Limit", "", 30),
        ("igpu_min", "Minimum iGPU Clock Limit", "MHz", 400),
        ("igpu_max", "Maximum iGPU Clock Limit", "MHz", 2000),
        ("min_cpu_clk", "Minimum CPU Clock Limit", "MHz", 1200),
        ("nv_max_clk", "Max GPU Clock", "MHz", 4000),
        ("nv_core_offset", "GPU Core Offset", "MHz", 0),
        ("nv_mem_offset", "GPU Mem Offset", "MHz", 0),
    )

    _HINTS = {
        "max_temp": "Controls the max temperature limit adaptive mode is allowed to set",
        "power": "Controls the max power limit adpative mode is allowed to set",
        "co_max": "Controls the max negative curve optimiser limit adpative mode is allowed to set",
        "igpu_min": "Controls the minimum iGPU clock speed adaptive mode is allowed to set",
        "igpu_max": "Controls the maximum iGPU clock speed adaptive mode is allowed to set",
        "min_cpu_clk": "Controls the minimum CPU clock speed at which adaptive mode will start throttling iGPU clocks",
        "nv_max_clk": "Controls the maximum voltage your GPU will run within the Frequency/Voltage curve based on clock speed. You can undervolt your NVIDIA GPU by lowering this clock speed below stock and increasing the core clock offset. Start at your GPU's rated boost clock and work down. To reset it, set it to the maximum possible clock the slider allows.",
        "nv_core_offset": "Controls the clock offset for your NVIDIA GPU's core clock",
        "nv_mem_offset": "Controls the clock offset for your NVIDIA GPU's VRAM clock",
    }

    _RANGES = {
        "max_temp":      (50, 105),
        "power":         (5, 300),
        "co_max":        (0, 30),
        "igpu_min":      (200, 2000),
        "igpu_max":      (200, 2000),
        "min_cpu_clk":   (400, 4000),
        "nv_max_clk":    (100, 4000),
        "nv_core_offset": (-1000, 1000),
        "nv_mem_offset":  (-1000, 1000),
    }

    _CORE_KEYS = ("max_temp", "power", "co_max", "igpu_min", "igpu_max", "min_cpu_clk")
    _NV_KEYS = ("nv_max_clk", "nv_core_offset", "nv_mem_offset")

    _running = False
    _running_preset = ""
    _has_asus = False
    _has_nvidia = False

    def _num_field(self, key: str) -> Vertical:
        _, label, unit, default = next(f for f in self._FIELDS if f[0] == key)
        head = Static(label, classes="field_name", markup=False)
        hint = self._HINTS[key]
        rng = self._RANGES.get(key)
        if rng:
            rng_str = f"Range: {rng[0]} to {rng[1]} {unit}".rstrip()
            hint = f"{hint}\n{rng_str}"
        desc = Static(hint, classes="field_hint", markup=False)
        box = Input(str(default), type="integer", restrict=r"-?\d*",
                    id=f"adaptive_f_{key}", classes="card_value")
        row = Horizontal(box, Static(unit, classes="unit"), classes="card_controls")
        return Vertical(head, desc, row, classes="field_card")

    def _toggle_field(self, key: str, label: str, hint: str, default: bool = True) -> Vertical:
        head = Static(label, classes="field_name", markup=False)
        desc = Static(hint, classes="field_hint", markup=False)
        row = Horizontal(Switch(value=default, id=f"adaptive_enable_{key}"),
                         Label("Enabled", classes="set_label"), classes="card_controls")
        return Vertical(head, desc, row, classes="field_card")

    def _interval_field(self) -> Vertical:
        head = Static("Polling Rate", classes="field_name", markup=False)
        desc = Static("How often adaptive mode polls sensors and adjusts, in seconds.",
                      classes="field_hint", markup=False)
        box = Input(self._current_interval(), id="adaptive_interval",
                    classes="card_value", restrict=r"\d*")
        row = Horizontal(box, Static("s", classes="unit"), classes="card_controls")
        return Vertical(head, desc, row, classes="field_card")

    def _asus_mode_field(self) -> Vertical:
        from Assets.system import platformctl
        head = Static("ASUS Performance Mode", classes="field_name", markup=False)
        desc = Static("Silent, Balanced or Turbo.",
                      classes="field_hint", markup=False)
        sel = Select([(c, i) for i, c in enumerate(platformctl.ASUS_MODE_CHOICES)],
                     value=1, allow_blank=False, id="adaptive_asus_mode")
        return Vertical(head, desc, Horizontal(sel, classes="card_controls"), classes="field_card")

    def compose(self) -> ComposeResult:
        from Assets.tuning import adaptivepreset, custom
        from Assets.system import platformctl
        self._has_asus = platformctl.asus_available()
        self._has_nvidia = custom.has_nvidia()
        names = adaptivepreset.names()
        with Vertical(id="editor_topbar"):
            with Horizontal(classes="topbar_title_row"):
                yield Static("Adaptive Mode", classes="card_title")
            with Horizontal(classes="topbar_row"):
                yield Select([(n, n) for n in names], prompt="Saved Presets",
                             id="adaptive_select", allow_blank=True)
                yield Input(placeholder="Preset name", id="adaptive_name")
            with Horizontal(classes="topbar_row"):
                yield Button("Save", id="adaptive_save", variant="primary")
                yield Button("Duplicate", id="adaptive_duplicate")
                yield Button("Delete", id="adaptive_delete", variant="error")
                yield Button("Start", id="adaptive_start", variant="success")
        with Vertical(classes="settings_card"):
            yield Collapsible(
                self._interval_field(),
                self._num_field("max_temp"),
                self._num_field("power"),
                self._toggle_field("co", "Curve Optimiser",
                                   "Enable adaptive Curve Optimiser tuning.", False),
                self._num_field("co_max"),
                title="Basic Adaptive Mode Settings", collapsed=True)
            yield Collapsible(
                self._toggle_field("igpu", "Turbo Boost Overdrive iGPU",
                                   "Enable adaptive Turbo Boost Overdrive iGPU tuning.", False),
                self._num_field("igpu_max"),
                self._num_field("igpu_min"),
                self._num_field("min_cpu_clk"),
                title="Turbo Boost Overdrive iGPU Settings", collapsed=True)
            if self._has_asus:
                yield Collapsible(
                    self._toggle_field("asus", "ASUS Power Profile",
                                       "Enable adaptive ASUS power profile switching.", False),
                    self._asus_mode_field(),
                    title="ASUS Power Profile", collapsed=True)
            if self._has_nvidia:
                yield Collapsible(
                    self._toggle_field("nvidia", "NVIDIA GPU Tuning",
                                       "Enable adaptive NVIDIA GPU tuning.", False),
                    self._num_field("nv_max_clk"), self._num_field("nv_core_offset"),
                    self._num_field("nv_mem_offset"),
                    title="NVIDIA GPU Tuning", collapsed=True)

    def on_mount(self) -> None:
        from Assets.tuning import adaptivepreset
        active = cfg.get("Adaptive", "preset", "")
        if active and active in adaptivepreset.names():
            sel = self.query_one("#adaptive_select", Select)
            if sel.value != active:
                try:
                    sel.value = active
                except Exception:
                    pass
        self._refresh_status()
        self.set_interval(1.0, self._refresh_status)

    _ignore_cache_until: float = 0.0

    def _refresh_status(self) -> None:
        if time.monotonic() < self._ignore_cache_until:
            return
        adaptive = self.app._last_status.get("adaptive", {})
        self._render_status(bool(adaptive.get("running")), adaptive.get("preset") or "")

    def _render_status(self, running: bool, preset: str) -> None:
        self._running = running
        self._running_preset = preset
        self.query_one("#adaptive_start", Button).label = "Stop" if running else "Start"
        if running and preset:
            sel = self.query_one("#adaptive_select", Select)
            if sel.value != preset:
                try:
                    sel.value = preset
                except Exception:
                    pass

    def _collect_preset(self):
        from Assets.tuning.adaptivepreset import AdaptivePreset
        def val(key):
            try:
                return int(self.query_one(f"#adaptive_f_{key}", Input).value)
            except ValueError:
                return 0
        preset = AdaptivePreset(
            max_temp=val("max_temp"), power=val("power"),
            co_max=val("co_max"), igpu_min=val("igpu_min"), igpu_max=val("igpu_max"),
            min_cpu_clk=val("min_cpu_clk"),
            enable_co=self.query_one("#adaptive_enable_co", Switch).value,
            enable_igpu=self.query_one("#adaptive_enable_igpu", Switch).value)
        if self._has_asus:
            preset.enable_asus = self.query_one("#adaptive_enable_asus", Switch).value
            mode = self.query_one("#adaptive_asus_mode", Select).value
            preset.asus_mode = mode if isinstance(mode, int) else 1
        if self._has_nvidia:
            preset.enable_nvidia = self.query_one("#adaptive_enable_nvidia", Switch).value
            preset.nv_max_clk = val("nv_max_clk")
            preset.nv_core_offset = val("nv_core_offset")
            preset.nv_mem_offset = val("nv_mem_offset")
        return preset

    def _current_interval(self) -> str:
        return cfg.get("Adaptive", "interval", "2") or "2"

    def _persist_run(self, target: str) -> None:
        try:
            value = int(self.query_one("#adaptive_interval", Input).value)
        except ValueError:
            value = 2
        cfg.set_config("Adaptive", "interval", str(min(8, max(1, value))))
        if target:
            cfg.set_config("Adaptive", "preset", target)
        cfg.save()

    def _refresh_presets(self, select) -> None:
        from Assets.tuning import adaptivepreset
        names = adaptivepreset.names()
        sel = self.query_one("#adaptive_select", Select)
        sel.set_options([(n, n) for n in names])
        if select and select in names:
            sel.value = select
            self.query_one("#adaptive_name", Input).value = select
        else:
            self.query_one("#adaptive_name", Input).value = ""

    def _load_preset(self, name: str) -> None:
        from Assets.tuning import adaptivepreset
        preset = adaptivepreset.get(name)
        if preset is None:
            return
        self.query_one("#adaptive_name", Input).value = name
        for key in self._CORE_KEYS:
            self.query_one(f"#adaptive_f_{key}", Input).value = str(getattr(preset, key))
        self.query_one("#adaptive_enable_co", Switch).value = preset.enable_co
        self.query_one("#adaptive_enable_igpu", Switch).value = preset.enable_igpu
        if self._has_asus:
            self.query_one("#adaptive_enable_asus", Switch).value = preset.enable_asus
            self.query_one("#adaptive_asus_mode", Select).value = preset.asus_mode
        if self._has_nvidia:
            self.query_one("#adaptive_enable_nvidia", Switch).value = preset.enable_nvidia
            for key in self._NV_KEYS:
                self.query_one(f"#adaptive_f_{key}", Input).value = str(getattr(preset, key))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "adaptive_select" and isinstance(event.value, str):
            self._load_preset(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from dataclasses import asdict
        from Assets.core import ipc
        from Assets.tuning import adaptivepreset
        bid = event.button.id or ""
        if bid == "adaptive_save":
            name = self.query_one("#adaptive_name", Input).value.strip()
            if not name:
                self.app.notify("Enter a preset name first.", title="Save preset",
                                severity="warning")
                return
            preset = self._collect_preset()
            adaptivepreset.save(name, preset)
            self._refresh_presets(name)
            if self._running and name == self._running_preset:
                self._persist_run(name)
                ipc.get_client().adaptive_start(name, asdict(preset))
                self._render_status(True, name)
                self._ignore_cache_until = time.monotonic() + 2.0
                self.app.notify(f"Preset '{name}' saved and applied.", title="Saved")
            else:
                self.app.notify(f"Preset '{name}' saved.", title="Saved")
        elif bid == "adaptive_duplicate":
            sel = self.query_one("#adaptive_select", Select).value
            base = self.query_one("#adaptive_name", Input).value.strip() or \
                (sel if isinstance(sel, str) else "")
            if not base:
                self.app.notify("Select or name a preset to duplicate.", title="Duplicate preset",
                                severity="warning")
                return
            existing = set(adaptivepreset.names())
            new_name, i = base, 2
            while new_name in existing:
                new_name = f"{base} ({i})"
                i += 1
            adaptivepreset.save(new_name, self._collect_preset())
            self._refresh_presets(new_name)
            self.app.notify(f"Duplicated to '{new_name}'.", title="Duplicated")
        elif bid == "adaptive_delete":
            sel = self.query_one("#adaptive_select", Select).value
            if not isinstance(sel, str):
                self.app.notify("Select a saved preset to delete.", title="Delete preset",
                                severity="warning")
                return
            adaptivepreset.delete(sel)
            self._refresh_presets(None)
            if cfg.get("Adaptive", "preset", "") == sel:
                cfg.set_config("Adaptive", "preset", "")
                cfg.save()
            if self._running and self._running_preset and \
                    self._running_preset not in adaptivepreset.names():
                ipc.get_client().adaptive_stop()
                self._render_status(False, "")
                self._ignore_cache_until = time.monotonic() + 2.0
                self.app.notify(f"Preset '{sel}' deleted, Adaptive Mode stopped.", title="Deleted")
            else:
                self.app.notify(f"Preset '{sel}' deleted.", title="Deleted")
        elif bid == "adaptive_start":
            client = ipc.get_client()
            if self._running:
                result = client.adaptive_stop()
                if result.get("ok"):
                    self._persist_run("")
                    self._render_status(False, "")
                    self._ignore_cache_until = time.monotonic() + 2.0
                    self.app.notify("Adaptive Mode stopped.", title="Adaptive Mode")
                else:
                    self.app.notify(result.get("error", "Failed to stop Adaptive Mode."),
                                    title="Adaptive Mode", severity="error")
            else:
                name = self.query_one("#adaptive_name", Input).value.strip()
                sel = self.query_one("#adaptive_select", Select).value
                if name:
                    target = name
                elif isinstance(sel, str):
                    target = sel
                else:
                    self.app.notify("Select or save a preset first.", title="Adaptive Mode",
                                    severity="warning")
                    return
                preset = self._collect_preset()
                if name:
                    adaptivepreset.save(name, preset)
                    self._refresh_presets(name)
                self._persist_run(target)
                result = client.adaptive_start(target, asdict(preset))
                if result.get("ok"):
                    self._render_status(True, target)
                    self._ignore_cache_until = time.monotonic() + 2.0
                    self.app.notify(f"Adaptive Mode started: {target}.", title="Adaptive Mode")
                else:
                    self.app.notify(result.get("error", "Failed to start Adaptive Mode."),
                                    title="Adaptive Mode", severity="error")
