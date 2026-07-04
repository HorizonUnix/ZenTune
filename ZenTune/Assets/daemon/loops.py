from __future__ import annotations

import threading
import time

from Assets.core import config as cfg
from Assets.daemon.util import (
    PresetState, _apply_via_smu, _clock_boottime, _dn, _fmt_duration,
    _on_ac, _resolve_preset_args, log,
)

_STOP_LOOP_TIMEOUT_S: int = 10
_POWER_MONITOR_POLL_S: int = 2
_SUSPEND_MONITOR_POLL_S: int = 1
_SUSPEND_GAP_THRESHOLD_S: float = 1.0


class LoopsMixin:
    def _effective_mode_args(
        self, base_mode: str, base_args: str, automation: bool,
        on_ac: bool | None = None, keep_on_empty: bool = False,
    ) -> tuple[str, str]:
        if not automation:
            return base_mode, base_args

        cfg.load()
        current_ac = _on_ac() if on_ac is None else on_ac
        power_state = "AC" if current_ac else "Battery"
        config_key = "OnAC" if current_ac else "OnBattery"
        preset_name = cfg.get("Automations", config_key, "")
        base_mode = base_mode or "Unknown"

        if not preset_name:
            if keep_on_empty:
                log.debug("Automation slot '%s' is empty, keeping current settings.", config_key)
                return base_mode, ""
            log.debug(
                "Automation slot '%s' is empty, falling back to base preset '%s'.",
                config_key, base_mode,
            )
            return base_mode, base_args

        result = _resolve_preset_args(preset_name)
        if result is None:
            if keep_on_empty:
                log.warning(
                    "Automation preset '%s' (slot: %s) not found, keeping current settings.",
                    preset_name, config_key,
                )
                return base_mode, ""
            log.warning(
                "Automation preset '%s' (slot: %s) not found, falling back to '%s'.",
                preset_name, config_key, base_mode,
            )
            return base_mode, base_args

        log.debug(
            "Automation resolved: slot=%s power=%s → preset='%s'",
            config_key, power_state, preset_name,
        )
        return result

    def _apply_once(self, args: str, mode: str, *, reason: str = "") -> tuple[str, bool]:
        if not args:
            log.debug("Apply skipped: no args for preset '%s'.", mode)
            return "", False
        output, rejected = _apply_via_smu(args, mode)
        with self._lock:
            self._mode = mode
            self._args = args
            self._last_output = output
            self._last_rejected = rejected
        if reason and not rejected:
            log.info("Applied preset '%s' (%s).", _dn(mode), reason)
        return output, rejected

    def _loop_body(
        self, args: str, mode: str, interval: int, automation: bool
    ) -> None:
        self._stop_evt.clear()
        log.debug(
            "Reapply loop started (mode='%s', interval=%ds, automation=%s).",
            mode, interval, automation,
        )
        while not self._stop_evt.wait(interval):
            try:
                if self._adaptive_running:
                    continue
                on_ac = _on_ac()
                eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
                changed = eff_mode != self._last_logged_mode
                log.debug(
                    "Reapply tick: preset '%s' (power=%s).",
                    eff_mode, "AC" if on_ac else "Battery",
                )
                reason = ""
                if changed:
                    reason = f"automations switched preset, now on {'AC' if on_ac else 'battery'}"
                self._apply_once(eff_args, eff_mode, reason=reason)
                if changed:
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                log.warning("Reapply loop error: %s", exc)
        with self._lock:
            self._running_loop = False
        log.debug("Reapply loop exited.")

    def _stop_loop(self) -> None:
        self._stop_evt.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)
            if self._loop_thread.is_alive():
                log.warning(
                    "Reapply thread did not stop within %ds; may still be running.",
                    _STOP_LOOP_TIMEOUT_S,
                )

    def _monitor_body(self, args: str, mode: str) -> None:
        self._stop_monitor_evt.clear()
        self._last_ac_state = _on_ac()
        log.debug(
            "Power-state monitor started (base='%s', poll=%ds, initial=%s).",
            mode, _POWER_MONITOR_POLL_S,
            "AC" if self._last_ac_state else "Battery",
        )
        while not self._stop_monitor_evt.wait(_POWER_MONITOR_POLL_S):
            try:
                if self._adaptive_running:
                    self._last_ac_state = _on_ac()
                    continue
                current_ac = _on_ac()
                if current_ac != self._last_ac_state:
                    prev_state = "AC" if self._last_ac_state else "battery"
                    new_state = "AC" if current_ac else "battery"
                    self._last_ac_state = current_ac
                    eff_mode, eff_args = self._effective_mode_args(
                        mode, args, automation=True, on_ac=current_ac, keep_on_empty=True
                    )
                    self._apply_once(
                        eff_args, eff_mode,
                        reason=f"power source changed from {prev_state} to {new_state}",
                    )
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                log.warning("Power-state monitor error: %s", exc)
        log.debug("Power-state monitor exited.")

    def _stop_monitor(self) -> None:
        self._stop_monitor_evt.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _suspend_monitor_body(self) -> None:
        self._stop_suspend_evt.clear()
        try:
            last_boottime_offset = _clock_boottime() - time.monotonic()
        except OSError as exc:
            log.warning(
                "CLOCK_BOOTTIME unavailable, suspend/resume detection disabled: %s", exc
            )
            return

        log.debug(
            "Suspend monitor started (poll=%ds, threshold=%.1fs).",
            _SUSPEND_MONITOR_POLL_S, _SUSPEND_GAP_THRESHOLD_S,
        )
        while not self._stop_suspend_evt.wait(_SUSPEND_MONITOR_POLL_S):
            try:
                current_boottime_offset = _clock_boottime() - time.monotonic()
                slept = current_boottime_offset - last_boottime_offset
                if slept > _SUSPEND_GAP_THRESHOLD_S:
                    cfg.load()
                    preset_name = cfg.get("Automations", "OnResume", "")
                    if not preset_name:
                        log.info(
                            "Woke from suspend (slept ~%s), no On Resume preset configured.",
                            _fmt_duration(slept),
                        )
                    else:
                        result = _resolve_preset_args(preset_name)
                        if result:
                            mode, args = result
                            self._apply_once(
                                args, mode,
                                reason=f"woke from suspend after ~{_fmt_duration(slept)}",
                            )
                            self._last_logged_mode = mode
                        else:
                            log.warning(
                                "Woke from suspend, but the On Resume preset '%s' no longer exists; nothing applied.",
                                _dn(preset_name),
                            )
                last_boottime_offset = current_boottime_offset
            except Exception as exc:
                log.warning("Suspend monitor tick error: %s", exc)
        log.debug("Suspend monitor exited.")

    def _start_suspend_monitor(self) -> None:
        self._stop_suspend_monitor()
        self._stop_suspend_evt.clear()
        self._suspend_thread = threading.Thread(
            target=self._suspend_monitor_body,
            daemon=True,
            name="zentune-suspend-monitor",
        )
        self._suspend_thread.start()
        log.info("Watching for suspend/resume.")

    def _stop_suspend_monitor(self) -> None:
        self._stop_suspend_evt.set()
        if self._suspend_thread and self._suspend_thread.is_alive():
            self._suspend_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _start_monitor(self, args: str, mode: str) -> None:
        self._stop_monitor()
        self._stop_monitor_evt.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_body,
            args=(args, mode),
            daemon=True,
            name="zentune-power-monitor",
        )
        self._monitor_thread.start()
        log.info("Watching for AC/battery changes.")

    def apply_preset_state_once(self, state: PresetState, reason: str = "restoring saved settings") -> str:
        output, _ = self._apply_once(state.args, state.mode, reason=reason)
        return output

    def start_auto_reapply(self, state: PresetState) -> dict:
        return self._cmd_apply_loop({
            "args": state.args,
            "mode": state.mode,
            "interval": state.interval,
            "automation": state.automation,
        })

