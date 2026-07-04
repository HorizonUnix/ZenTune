from __future__ import annotations

import json
import logging
import threading

from Assets.core import config as cfg
from Assets.daemon.util import _dn, _load_saved_preset, _on_ac, log


class CommandsMixin:
    def _cmd_reload_config(self, _msg: dict) -> dict:
        cfg.load()
        debug = cfg.is_debug()
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
        log.info("Config reloaded (debug=%s)", debug)
        return {"ok": True}

    def _cmd_reset_state(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        with self._lock:
            self._mode = ""
            self._args = ""
            self._automation = False
            self._interval = 3
            self._running_loop = False
            self._last_output = ""
            self._last_rejected = False
        self._last_logged_mode = ""
        cfg.load()
        logging.getLogger().setLevel(logging.DEBUG if cfg.is_debug() else logging.INFO)
        log.info("Daemon state reset to defaults.")
        return {"ok": True}

    def _cmd_ping(self, _msg: dict) -> dict:
        return {"ok": True, "version": cfg.LOCAL_VERSION}

    def _cmd_apply(self, msg: dict) -> dict:
        try:
            mode = msg.get("mode", "Unknown")
            args = msg.get("args", "")
            output, rejected = self._apply_once(args, mode, reason="selected in the app")
            self._last_logged_mode = mode
            return {"ok": True, "output": output, "rejected": rejected}
        except Exception as exc:
            log.error("apply command failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _cmd_apply_loop(self, msg: dict) -> dict:
        args = msg.get("args", "")
        mode = msg.get("mode", "Unknown")
        interval = cfg.parse_interval(msg.get("interval", cfg.get("Settings", "Time", "3")), default=3)
        automation = bool(msg.get("automation", False))

        log.debug(
            "apply_loop: mode='%s', interval=%ds, automation=%s.",
            mode, interval, automation,
        )

        self._stop_loop()
        self._stop_monitor()

        with self._lock:
            self._automation = automation
            self._interval = interval
            self._running_loop = True

        on_ac = _on_ac()
        eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
        try:
            output, rejected = self._apply_once(eff_args, eff_mode, reason="starting auto-reapply")
            self._last_logged_mode = eff_mode
        except Exception as exc:
            with self._lock:
                self._running_loop = False
            log.error("Initial apply failed before starting reapply loop: %s", exc)
            return {"ok": False, "error": str(exc)}

        if automation:
            log.info(
                "Auto-reapply on, every %ds. Automations pick the preset (AC: '%s', battery: '%s').",
                interval,
                _dn(cfg.get("Automations", "OnAC", "")),
                _dn(cfg.get("Automations", "OnBattery", "")),
            )
        else:
            log.info("Auto-reapply on, preset '%s' will be re-applied every %ds.", _dn(mode), interval)

        self._loop_thread = threading.Thread(
            target=self._loop_body,
            args=(args, mode, interval, automation),
            daemon=True,
            name="zentune-reapply",
        )
        self._loop_thread.start()
        return {"ok": True, "output": output, "rejected": rejected}

    def _cmd_stop_loop(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        with self._lock:
            self._running_loop = False
            mode = self._mode
            args = self._args
        log.info("Auto-reapply turned off.")
        cfg.load()
        if cfg.get("Automations", "OnAC", "") or cfg.get("Automations", "OnBattery", ""):
            self._start_monitor(args, mode)
        return {"ok": True}

    def _cmd_status(self, _msg: dict) -> dict:
        from zenmaster.smu import active_backend
        on_ac = _on_ac()
        with self._lock:
            status = {
                "ok": True,
                "running_loop": self._running_loop,
                "mode": self._mode,
                "args": self._args,
                "automation": self._automation,
                "interval": self._interval,
                "on_ac": on_ac,
                "last_output": self._last_output,
                "last_rejected": self._last_rejected,
                "version": cfg.LOCAL_VERSION,
                "backend": active_backend(),
                "adaptive": {
                    "running": self._adaptive_running,
                    "preset": self._adaptive_preset_name,
                    "applied": self._adaptive_applied,
                },
            }
        return status

    def _cmd_apply_saved(self, _msg: dict) -> dict:
        try:
            state = _load_saved_preset()
        except Exception as exc:
            log.error("Failed to load saved preset: %s", exc)
            return {"ok": False, "error": str(exc)}
        self._stop_loop()
        self._stop_monitor()

        if state is None:
            with self._lock:
                self._automation = False
            return {"ok": False, "error": "Saved preset not found"}

        with self._lock:
            self._automation = state.automation

        if state.reapply:
            log.debug(
                "apply_saved: reapply=on, automation=%s → starting loop.",
                state.automation,
            )
            return self.start_auto_reapply(state)

        if state.automation:
            on_ac = _on_ac()
            eff_mode, eff_args = self._effective_mode_args(
                state.mode, state.args, automation=True, on_ac=on_ac
            )
            output, _ = self._apply_once(eff_args, eff_mode, reason="restoring saved settings")
            self._last_logged_mode = eff_mode
            log.debug("apply_saved: reapply=off, automation=on → starting monitor.")
            self._start_monitor(state.args, state.mode)
            return {"ok": True, "output": output}

        log.debug("apply_saved: reapply=off, automation=off → single apply.")
        output = self.apply_preset_state_once(state)
        return {"ok": True, "output": output}


    def handle(self, raw: str) -> str:
        try:
            msg = json.loads(raw)
            cmd = msg.get("cmd", "")
            func = self._dispatch.get(cmd)
            if func is None:
                log.warning("Unknown IPC command: '%s'.", cmd)
                return json.dumps({"ok": False, "error": f"unknown command: {cmd!r}"})
            log.debug("IPC command: '%s'.", cmd)
            resp = func(msg)
        except Exception as exc:
            log.error("IPC handler error: %s", exc)
            resp = {"ok": False, "error": str(exc)}
        return json.dumps(resp)
