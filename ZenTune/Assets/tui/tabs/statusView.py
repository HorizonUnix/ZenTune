from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Static

from Assets.core import config as cfg
from Assets.core import platform as plat


def _strip(name: str) -> str:
    return (name or "").removesuffix("_custom_preset")


class StatusTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(id="status_panel"):
            yield Static("Daemon status", classes="card_title")
            yield Static("", id="status_info")
        with Vertical(id="status_smu_card"):
            yield Static("Output", id="status_smu_head", classes="card_title")
            yield Static("", id="status_smu")
            yield Button("Copy to clipboard", id="status_smu_copy")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "status_smu_copy":
            return
        text = str(self.query_one("#status_smu", Static).content)
        self.app.copy_to_clipboard(text)
        self.app.notify("Copied to clipboard.", title="Copy")

    def on_mount(self) -> None:
        self._timer = None
        self._watch = None
        self._last_ac = None
        self.refresh_status()

    def on_show(self) -> None:
        self.refresh_status()
        self._reschedule()

    def on_hide(self) -> None:
        self._stop_timers()

    def _stop_timers(self) -> None:
        for t in (self._timer, self._watch):
            if t is not None:
                t.stop()
        self._timer = None
        self._watch = None

    def _reschedule(self) -> None:
        from Assets.tui.helpers import on_ac
        self._stop_timers()
        self._last_ac = on_ac()
        self._watch = self.set_interval(2.0, self._check_power)
        self._timer = self.set_interval(1.0, self.refresh_status)

    def _check_power(self) -> None:
        from Assets.tui.helpers import on_ac
        ac = on_ac()
        if ac != self._last_ac:
            self._last_ac = ac
            self.refresh_status()

    def refresh_status(self) -> None:
        st = self.app._last_status
        self._draw_status(st, st.get("adaptive", {}))

    def _draw_status(self, st: dict, adaptive: dict) -> None:
        panel = self.query_one("#status_info", Static)
        head = self.query_one("#status_smu_head", Static)
        smu = self.query_one("#status_smu", Static)

        if not st.get("ok"):
            panel.update(
                "[b]System[/b]\n"
                "  Daemon      [yellow]Stopped[/]\n\n"
                "[dim]Install or start it from the Settings tab.[/dim]"
            )
            head.update("SMU output")
            smu.update("")
            return

        on_ac = st.get("on_ac")
        loop = st.get("running_loop")
        automation = st.get("automation")
        mode = _strip(st.get("mode") or "")
        interval = st.get("interval", "?")
        from Assets.tuning.power import current_preset_label
        profile = current_preset_label()

        def row(label, value):
            return f"  {label:<12}{value}"

        backend = st.get("backend", "?")

        lines = [
            "[b]System[/b]",
            row("Daemon", "[green]Running[/]"),
            row("Power", "AC" if on_ac else "Battery"),
            row("Backend", backend),
            "",
            "[b]Preset[/b]",
            row("Active", mode or "[dim]—[/]"),
        ]
        if profile:
            lines.append(row("Profile", profile))
        if loop:
            lines.append(row("Re-apply", "[green]ON[/]"))
            lines.append(row("Interval", f"every {interval}s"))
        else:
            lines.append(row("Re-apply", "[dim]OFF[/]"))
        lines.append("")

        resume = _strip(cfg.get("Automations", "OnResume", ""))
        lines.append("[b]Automations[/b]")
        if automation:
            ac_p = _strip(cfg.get("Automations", "OnAC", ""))
            bat_p = _strip(cfg.get("Automations", "OnBattery", ""))
            lines.append(row("Status", "[green]ON[/]"))
            if ac_p:
                lines.append(row("On AC", ac_p))
            if bat_p:
                lines.append(row("On Battery", bat_p))
        else:
            lines.append(row("Status", "[dim]OFF[/]"))
        if resume:
            lines.append(row("On Resume", resume))
        lines.append("")

        if not plat.IS_MACOS:
            lines.append("[b]Adaptive[/b]")
            if adaptive.get("running"):
                lines.append(row("Status", "[green]ON[/]"))
                preset = adaptive.get("preset")
                if preset:
                    lines.append(row("Preset", preset))
                try:
                    poll = int(cfg.get("Adaptive", "interval", "2") or "2")
                except ValueError:
                    poll = 2
                lines.append(row("Poll", f"every {poll}s"))
                applied = adaptive.get("applied")
                if applied:
                    lines.append(row("Applied", applied))
            else:
                lines.append(row("Status", "[dim]OFF[/]"))

        panel.update("\n".join(lines))

        out = st.get("last_output") or ""
        if not out:
            head.update("Output")
            smu.update("[dim]No preset applied yet.[/]")
            return
        head.update("[yellow]Output: some commands were rejected[/]"
                    if st.get("last_rejected") else "[green]Output: OK[/]")
        smu.update(out)
