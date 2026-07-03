from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Select, Static

from Assets.tuning import automations as au


class AutomationsTab(VerticalScroll):
    _SLOTS = (
        ("ac", "Preset on Battery Charge",
         "Applied automatically when you plug in the charger.",
         au.get_ac_preset, au.set_ac_preset),
        ("battery", "Preset on Battery Discharge",
         "Applied automatically when you unplug and run on battery.",
         au.get_battery_preset, au.set_battery_preset),
        ("resume", "Preset on System Resume",
         "Applied automatically when the system wakes from sleep/hibernation.",
         au.get_resume_preset, au.set_resume_preset),
    )

    def _slot_options(self) -> list[tuple[str, str]]:
        from Assets.tuning.power import get_presets
        from Assets.tuning.custom import get_custom_preset_names, display_name
        opts = [("None", "")]
        opts += [(f"PM - {n} Preset", n) for n in get_presets()]
        opts += [(display_name(n), n) for n in get_custom_preset_names()]
        return opts

    def compose(self) -> ComposeResult:
        options = self._slot_options()
        valid = {v for _, v in options}
        with Vertical(classes="settings_card"):
            yield Static("Automations", classes="card_title")
            for slot_id, label, desc, getter, _ in self._SLOTS:
                cur = getter() or ""
                with Vertical(classes="auto_slot"):
                    yield Static(label, classes="field_name")
                    yield Static(desc, classes="field_hint")
                    yield Select(list(options), value=cur if cur in valid else "",
                                 allow_blank=False, id=f"slot-{slot_id}")

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.control.id or ""
        if not sid.startswith("slot-"):
            return
        slot_id = sid[len("slot-"):]
        slot = next((s for s in self._SLOTS if s[0] == slot_id), None)
        if slot is None:
            return
        getter, setter = slot[3], slot[4]
        value = event.value if isinstance(event.value, str) else ""
        if value == getter():
            return
        setter(value)
        if slot_id == "resume":
            self._reload()
        else:
            self._notify()

    @work(thread=True, exclusive=True, group="auto")
    def _notify(self) -> None:
        au._notify_daemon()

    @work(thread=True, exclusive=True, group="auto")
    def _reload(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.reload_config()
