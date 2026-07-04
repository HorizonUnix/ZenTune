from __future__ import annotations

import os
import threading
from dataclasses import fields as dataclass_fields
from pathlib import Path

from Assets.core import config as cfg
from Assets.core import platform as plat
from Assets.core.platform import RUNTIME_DIR
from Assets.daemon.loops import _STOP_LOOP_TIMEOUT_S
from Assets.daemon.util import log

ADAPTIVE_SESSION_FILE = f"{RUNTIME_DIR}/{cfg.APP_NAME}_adaptive"


def _mark_adaptive_session(active: bool) -> None:
    try:
        if active:
            Path(ADAPTIVE_SESSION_FILE).touch()
        else:
            os.remove(ADAPTIVE_SESSION_FILE)
    except OSError:
        pass


class AdaptiveMixin:
    def _build_adaptive_args(self, state, preset, sample, caps):
        from Assets.engine import adaptive
        is_apu = cfg.get("Info", "Type") == "Amd_Apu"
        if sample.cpu_load is None:
            log.debug("Adaptive args skipped: CPU load unavailable this tick.")
            return ""
        temp = int(sample.cpu_temp) if sample.cpu_temp is not None else 0
        load = int(sample.cpu_load)
        parts = []
        if state.tick < 2:
            cmd = ""
            for _ in range(3):
                step = adaptive.update_power_limit(
                    state, temp, load, preset.power, preset.power - 5, preset.max_temp, is_apu)
                if step:
                    cmd = step
            if cmd:
                parts.append(cmd)
            state.tick += 1
            return " ".join(parts)
        cmd = adaptive.update_power_limit(
            state, temp, load, preset.power, 8, preset.max_temp, is_apu)
        if cmd:
            parts.append(cmd)
        if preset.enable_co:
            cmd = adaptive.curve_optimiser(state, load, preset.co_max)
            if cmd:
                parts.append(cmd)
        if (preset.enable_igpu and sample.igpu_load is not None and sample.igpu_clk is not None
                and sample.mem_clk is not None and sample.cpu_clk is not None):
            cmd = adaptive.update_igpu_clock(
                state, preset.igpu_max, preset.igpu_min, preset.max_temp,
                temp, int(sample.igpu_clk), int(sample.igpu_load), int(sample.mem_clk),
                int(sample.cpu_clk), preset.min_cpu_clk)
            if cmd:
                parts.append(cmd)
        return " ".join(parts)

    def _build_adaptive_static(self, preset):
        parts = []
        if preset.enable_asus:
            parts.append(f"--sys-asus-mode={preset.asus_mode}")
        if preset.enable_nvidia:
            parts.append(
                f"--nvidia-clocks={preset.nv_max_clk},{preset.nv_core_offset},"
                f"{preset.nv_mem_offset},{preset.nv_power_limit}")
        return " ".join(parts)

    def _adaptive_tick_args(self, sample):
        static = self._build_adaptive_static(self._adaptive_preset)
        dynamic = self._build_adaptive_args(
            self._adaptive_state, self._adaptive_preset, sample, self._adaptive_caps)
        return " ".join(part for part in (static, dynamic) if part)

    def _adaptive_body(self, interval):
        from Assets.system import sensors
        self._stop_adaptive_evt.clear()
        log.info("Adaptive loop started (preset='%s', interval=%ds).",
                 self._adaptive_preset_name, interval)
        sensors.sample()
        while not self._stop_adaptive_evt.wait(interval):
            try:
                sample = sensors.sample()
                merged = self._adaptive_tick_args(sample)
                if merged:
                    self._apply_once(merged, "Adaptive", reason="adaptive")
                with self._lock:
                    self._adaptive_sample = sample
                    self._adaptive_applied = merged or self._adaptive_applied
            except Exception as exc:
                log.warning("Adaptive loop error: %s", exc)
        with self._lock:
            self._adaptive_running = False
        log.debug("Adaptive loop exited.")

    def _stop_adaptive(self):
        self._stop_adaptive_evt.set()
        if self._adaptive_thread and self._adaptive_thread.is_alive():
            self._adaptive_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _adaptive_interval(self):
        try:
            value = int(cfg.get("Adaptive", "interval", "2"))
        except (TypeError, ValueError):
            value = 2
        return min(8, max(1, value))

    def _cmd_adaptive_start(self, msg):
        if plat.IS_MACOS:
            return {"ok": False, "error": "Adaptive Mode is not available on macOS."}
        from Assets.engine import adaptive
        from Assets.system import sensors
        from Assets.tuning import adaptivepreset
        cfg.load()
        name = msg.get("preset", "")
        values = msg.get("values")
        if values is not None:
            known = {f.name for f in dataclass_fields(adaptivepreset.AdaptivePreset)}
            preset = adaptivepreset.AdaptivePreset(
                **{k: v for k, v in values.items() if k in known})
        else:
            preset = adaptivepreset.get(name)
        if preset is None:
            return {"ok": False, "error": f"adaptive preset not found: {name!r}"}
        self._stop_adaptive()
        caps = sensors.capabilities()
        with self._lock:
            self._adaptive_preset_name = name
            self._adaptive_preset = preset
            self._adaptive_state = adaptive.AdaptiveState()
            self._adaptive_caps = caps
            self._adaptive_running = True
            self._adaptive_applied = ""
        interval = self._adaptive_interval()
        static = self._build_adaptive_static(preset)
        if static:
            self._apply_once(static, "Adaptive", reason="adaptive static settings")
        self._adaptive_thread = threading.Thread(
            target=self._adaptive_body, args=(interval,), daemon=True, name="zentune-adaptive")
        self._adaptive_thread.start()
        _mark_adaptive_session(True)
        return {"ok": True, "caps": sorted(caps)}

    def _cmd_adaptive_stop(self, _msg):
        self._stop_adaptive()
        with self._lock:
            self._adaptive_running = False
        _mark_adaptive_session(False)
        log.info("Adaptive turned off.")
        try:
            revert = self._cmd_apply_saved({})
        except Exception as exc:
            log.warning("Adaptive stop: revert to saved preset failed: %s", exc)
            return {"ok": True, "reverted": False}
        return {"ok": True, "reverted": bool(revert.get("ok"))}


