from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static

from Assets.core import config as cfg
from Assets.tuning import power
from Assets.tui.helpers import ADAPTIVE_ON_MSG

_COLOR = {"Eco": "eco", "Balance": "balance", "Performance": "perf", "Extreme": "extreme"}

_PRESET_HINTS: dict[str, str] = {
    "Eco": "This preset is designed to prioritize energy efficiency over performance. It sets power limits to conservative levels to reduce power consumption and heat generation, making it ideal for prolonged use in situations where maximizing battery life or minimizing energy usage is critical.",
    "Balance": "This preset aims to find a balance between performance and power consumption, providing a stable and efficient experience. This preset sets the power limits to a level that balances performance and power usage, without sacrificing too much of either.",
    "Performance": "This preset is optimized for maximum performance by increasing the power limits of the APU/CPU, which allows it to run at higher clock speeds for longer periods of time. This can result in improved system responsiveness and faster load times in applications that require high levels of processing power.",
    "Extreme": "This preset aims to push the power limits of the system to their maximum, allowing for the highest possible performance. This preset is designed for users who demand the most from their hardware and are willing to tolerate higher power consumption and potentially increased noise levels.",
}


class PowerTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        self._presets = power.get_presets()
        with Vertical(classes="settings_card"):
            yield Static("Premade Presets", classes="card_title")
            with Horizontal(id="preset_buttons"):
                for name in self._presets:
                    yield Button(name, id=f"pbtn-{name}",
                                 classes=f"preset_btn {_COLOR.get(name, '')}".strip())
        yield Static("", id="preset_detail")
        with Vertical(classes="settings_card", id="preset_command_card"):
            yield Static("SMU Command Output:", classes="card_title")
            yield Static("", id="preset_command")
            yield Button("Copy to clipboard", id="preset_command_copy")
            yield Static(
                "Note: Some commands may not be supported on every CPU family.",
                classes="field_hint", id="preset_command_note",
            )

    def on_mount(self) -> None:
        self._sync_active()

    async def on_show(self) -> None:
        await self._refresh_presets()
        self._sync_active()
        self._sync_from_daemon()

    async def _refresh_presets(self) -> None:
        presets = power.get_presets()
        if presets == self._presets:
            return
        self._presets = presets
        container = self.query_one("#preset_buttons", Horizontal)
        await container.remove_children()
        for name in self._presets:
            await container.mount(Button(name, id=f"pbtn-{name}",
                                          classes=f"preset_btn {_COLOR.get(name, '')}".strip()))

    def _sync_active(self) -> None:
        active = cfg.get("User", "Mode")
        self._highlight(active)
        if active in self._presets:
            self._show_detail(active)
        else:
            self._clear_detail()

    def _sync_from_daemon(self) -> None:
        st = self.app._last_status
        mode = (st.get("mode") or "").removesuffix("_custom_preset")
        if mode:
            self._highlight(mode)

    def _highlight(self, active: str) -> None:
        for name in self._presets:
            self.query_one(f"#pbtn-{name}", Button).set_class(name == active, "active")

    def _clear_detail(self) -> None:
        self.query_one("#preset_detail", Static).display = False
        self.query_one("#preset_command", Static).update("")
        self.query_one("#preset_command_card").display = False

    def _show_detail(self, name: str) -> None:
        desc = _PRESET_HINTS.get(name, "")
        detail = self.query_one("#preset_detail", Static)
        detail.update(f"[b]{name} Preset[/]\n\n{desc}")
        detail.display = True
        self.query_one("#preset_command", Static).update(self._presets.get(name, ""))
        self.query_one("#preset_command_card").display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "preset_command_copy":
            text = str(self.query_one("#preset_command", Static).content)
            self.app.copy_to_clipboard(text)
            self.app.notify("Copied to clipboard.", title="Copy")
            return
        if not bid.startswith("pbtn-"):
            return
        if self.app._last_status.get("adaptive", {}).get("running"):
            self.app.notify(ADAPTIVE_ON_MSG, title="Adaptive Mode active", severity="warning")
            return
        name = bid[len("pbtn-"):]
        self._show_detail(name)
        self._highlight(name)
        self.apply_preset_worker(self._presets[name], name)

    @work(thread=True, exclusive=True, group="apply")
    def apply_preset_worker(self, args: str, mode: str) -> None:
        from Assets.tuning.power import apply_preset
        result = apply_preset(args, mode)
        self.app.call_from_thread(self._notify_result, mode, result)

    def _notify_result(self, mode: str, result: dict) -> None:
        if not result.get("ok"):
            self.app.notify(result.get("error", "Failed to apply preset."),
                            title="Apply failed", severity="error")
            return
        if result.get("rejected"):
            self.app.notify(
                f"Preset '{mode}' applied, but some commands were rejected by the SMU. "
                "See the Status tab for details.",
                title="Applied with warnings", severity="warning")
        else:
            self.app.notify(f"Preset '{mode}' applied successfully.", title="Applied")
