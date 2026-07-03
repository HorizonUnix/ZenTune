from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Collapsible, Input, Select, Static, Switch

from Assets.core import config as cfg
from Assets.tuning.custom import (
    APU_SECTION_TITLES, DT_SECTION_TITLES,
    _default_fields_for_current_cpu, _supported_field_keys, _active_sections,
    _section_indices, clamp_field, _enforce_clk_clamp, build_args,
    save_preset, load_preset_fields, delete_preset, get_custom_preset_names, display_name,
    unique_preset_name,
)
from Assets.tui.modals import ConfirmModal
from Assets.tui.helpers import ADAPTIVE_ON_MSG


class CustomEditor(VerticalScroll):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.family = cfg.get("Info", "Family")
        self._cpu_type = cfg.get("Info", "Type")
        self._all_sections = DT_SECTION_TITLES if self._cpu_type == "Amd_Desktop_Cpu" else APU_SECTION_TITLES
        active = cfg.get("User", "Mode")
        names = [display_name(n) for n in get_custom_preset_names()]
        if active in names:
            self.fields = load_preset_fields(active) or _default_fields_for_current_cpu()
            self.preset_name = active
            self._loaded_name = active
        else:
            self.fields = _default_fields_for_current_cpu()
            self.preset_name = ""
            self._loaded_name = ""
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)

    def compose(self) -> ComposeResult:
        names = [display_name(n) for n in get_custom_preset_names()]
        sel_kwargs = {"value": self.preset_name} if self.preset_name in names else {}
        with Vertical(id="editor_topbar"):
            yield Static("Custom Presets", classes="card_title")
            with Horizontal(classes="topbar_row"):
                yield Select([(n, n) for n in names], prompt="Saved Presets",
                             id="preset_select", allow_blank=True, **sel_kwargs)
                yield Input(value=self.preset_name, placeholder="Preset name", id="new_name")
            with Horizontal(classes="topbar_row"):
                yield Button("Save", id="ed_save", variant="primary")
                yield Button("Duplicate", id="ed_duplicate")
                yield Button("Delete", id="ed_delete", variant="error")
                yield Button("Apply", id="ed_apply", variant="success")
        with Vertical(classes="settings_card"):
            for s in sorted(self.sections):
                rows = [self._field_row(fi) for fi in _section_indices(self.fields, s, self.supported)]
                yield Collapsible(*rows, title=self.sections[s], collapsed=True)

    def _field_row(self, fi: int) -> Vertical:
        f = self.fields[fi]
        head = Static(f["label"], classes="field_name", markup=False)
        hint = f.get("hint", "")
        if "choices" not in f and "min" in f and "max" in f:
            unit = f.get("unit", "")
            rng = f"Range: {f['min']} to {f['max']} {unit}".rstrip()
            hint = f"{hint}\n{rng}" if hint else rng
        desc = Static(hint, classes="field_hint", markup=False)
        toggle = Switch(value=f["enabled"], id=f"fcb-{fi}")
        if "choices" in f:
            control = Select([(c, i) for i, c in enumerate(f["choices"])],
                             value=f["value"], allow_blank=False, id=f"fsel-{fi}",
                             disabled=not f["enabled"])
            row = Horizontal(toggle, control, classes="card_controls")
        else:
            box = Input(value=str(f["value"]), type="integer", restrict=r"-?\d*",
                        id=f"fval-{fi}", classes="card_value", disabled=not f["enabled"])
            unit = Static(f.get("unit", ""), classes="unit")
            row = Horizontal(toggle, box, unit, classes="card_controls")
        return Vertical(head, desc, row, classes="field_card")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        cid = event.control.id or ""
        if cid.startswith("fcb-"):
            fi = int(cid[4:])
            self.fields[fi]["enabled"] = event.value
            for wid in (f"#fval-{fi}", f"#fsel-{fi}"):
                try:
                    self.query_one(wid).disabled = not event.value
                except NoMatches:
                    pass

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.control.id or ""
        if sid == "preset_select":
            if isinstance(event.value, str) and event.value != self.preset_name:
                self.run_worker(self._load_preset(event.value))
        elif sid.startswith("fsel-") and isinstance(event.value, int):
            self.fields[int(sid[5:])]["value"] = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        iid = event.control.id or ""
        if iid.startswith("fval-"):
            self._commit_input(int(iid[5:]), event.value, event.control)

    def _commit_input(self, fi: int, raw: str, widget: Input) -> None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return
        f = self.fields[fi]
        value = clamp_field(value, f)
        f["value"] = value
        _enforce_clk_clamp(self.fields, f["key"])
        widget.value = str(value)

    def _sync_inputs(self) -> None:
        for inp in self.query(Input):
            iid = inp.id or ""
            if iid.startswith("fval-"):
                fi = int(iid[5:])
                try:
                    self.fields[fi]["value"] = clamp_field(int(inp.value), self.fields[fi])
                except (TypeError, ValueError):
                    pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "ed_save":
            self._sync_inputs()
            name = self.query_one("#new_name", Input).value.strip() or self.preset_name
            if not name:
                self.app.notify("Enter a preset name first.", title="Save preset",
                                severity="warning")
                return
            replace = self._loaded_name if self._loaded_name and self._loaded_name != name else None
            self.preset_name = name
            self._do_save(name, replace)
        elif bid == "ed_apply":
            if self.app._last_status.get("adaptive", {}).get("running"):
                self.app.notify(ADAPTIVE_ON_MSG, title="Adaptive Mode active", severity="warning")
                return
            self._sync_inputs()
            self._do_apply()
        elif bid == "ed_duplicate":
            self._sync_inputs()
            source = self.query_one("#new_name", Input).value.strip() or self.preset_name
            if not source:
                self.app.notify("Select or name a preset to duplicate.", title="Duplicate preset",
                                severity="warning")
                return
            new_name = unique_preset_name(source)
            self.preset_name = new_name
            self._do_save(new_name)
            self.app.notify(f"Duplicated to '{new_name}'.", title="Duplicated")
        elif bid == "ed_delete":
            sel = self.query_one("#preset_select", Select)
            if not isinstance(sel.value, str):
                self.app.notify("Select a saved preset to delete.", title="Delete preset",
                                severity="warning")
                return
            name = sel.value
            self.app.push_screen(ConfirmModal(f"Delete preset '{name}'?"),
                                 lambda ok, n=name: self._do_delete(n) if ok else None)

    async def _load_preset(self, name: str) -> None:
        fields = load_preset_fields(name)
        if fields is None:
            self.app.notify(f"Preset '{name}' not found.", title="Load preset", severity="error")
            return
        self.fields = fields
        self.preset_name = name
        self._loaded_name = name
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)
        await self.recompose()

    @work(thread=True, exclusive=True, group="custom")
    def _do_save(self, name: str, replace: str | None = None) -> None:
        save_preset(name, self.fields, replace)
        self.app.call_from_thread(self._after_save, name)

    @work(thread=True, exclusive=True, group="custom")
    def _do_apply(self) -> None:
        args = build_args(self.fields, self._cpu_type)
        if not args.strip():
            self.app.call_from_thread(
                lambda: self.app.notify("No parameters are enabled.", title="Apply preset",
                                        severity="warning"))
            return
        from Assets.tuning.power import apply_preset
        name = self.preset_name or "Custom"
        result = apply_preset(args, name)
        if result.get("ok"):
            self.app.call_from_thread(self.app.notify, f"Preset '{name}' applied successfully.",
                                      title="Applied")
        else:
            err = result.get("error", "apply failed")
            self.app.call_from_thread(
                lambda: self.app.notify(err, title="Apply failed", severity="error"))

    @work(thread=True, exclusive=True, group="custom")
    def _do_delete(self, name: str) -> None:
        delete_preset(name)
        self.app.call_from_thread(self._after_delete, name)

    def _after_save(self, name: str) -> None:
        self._loaded_name = name
        self._refresh_presets(name)
        self.app.notify(f"Preset '{name}' saved.", title="Saved")

    def _after_delete(self, name: str) -> None:
        self.run_worker(self._reset_to_default())
        self.app.notify(f"Preset '{name}' deleted.", title="Deleted")

    async def _reset_to_default(self) -> None:
        self.preset_name = ""
        self._loaded_name = ""
        self.fields = _default_fields_for_current_cpu()
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)
        await self.recompose()

    def _refresh_presets(self, select: str | None) -> None:
        names = [display_name(n) for n in get_custom_preset_names()]
        sel = self.query_one("#preset_select", Select)
        sel.set_options([(n, n) for n in names])
        if select and select in names:
            sel.value = select
            self.query_one("#new_name", Input).value = select
