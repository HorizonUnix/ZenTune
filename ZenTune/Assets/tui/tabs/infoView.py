from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Collapsible, Static

from Assets.core import config as cfg
from Assets.core import platform as plat


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"  {label:<14}{value}" for label, value in pairs)


class HardwareTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("System Info", classes="card_title")
            if not plat.IS_MACOS:
                yield Collapsible(Static("Loading…", id="hw_device"),
                                  title="Device Information", collapsed=False)
            yield Collapsible(Static("Loading…", id="hw_processor"),
                              title="Processor Information", collapsed=False)

    def on_mount(self) -> None:
        self._load_static()

    @work(thread=True, exclusive=True, group="hw")
    def _load_static(self) -> None:
        if not plat.IS_MACOS:
            from Assets.core import hardware as hw
            dev = hw._parse_device_info()
            device = _rows([("Name", dev["name"]), ("Producer", dev["producer"]), ("Model", dev["model"])])
            self.app.call_from_thread(self.query_one("#hw_device", Static).update, device)
        processor = _rows([
            ("Processor", cfg.get("Info", "CPU")), ("Codename", cfg.get("Info", "Family")),
            ("Architecture", cfg.get("Info", "Architecture")), ("Signature", cfg.get("Info", "Signature"))])
        self.app.call_from_thread(self.query_one("#hw_processor", Static).update, processor)
