from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import zmq

_HERE = os.path.dirname(os.path.realpath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from Assets.core import config as cfg
from Assets.core import platform as plat

cfg.load()

from Assets.daemon.util import (
    log, _acquire_daemon_lock, _load_saved_preset, _on_ac, _DAEMON_LOCK_FILE,
)
from Assets.daemon.commands import CommandsMixin
from Assets.daemon.loops import LoopsMixin
from Assets.daemon.adaptive import AdaptiveMixin


def _smu_ready_message(driver: str, version: str) -> str:
    return f"{driver} driver ready (version {version})."


def _smu_unavailable_message(reason: str) -> str:
    if plat.IS_LINUX:
        return f"{reason}\nInstall guide: {cfg.RYZEN_SMU_WIKI_URL}"
    return reason


class PowerDaemon(CommandsMixin, LoopsMixin, AdaptiveMixin):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._suspend_thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._stop_monitor_evt = threading.Event()
        self._stop_suspend_evt = threading.Event()
        self._mode = ""
        self._args = ""
        self._automation = False
        self._interval = 3
        self._last_output = ""
        self._last_rejected = False
        self._running_loop = False
        self._last_logged_mode = ""
        self._last_ac_state: bool | None = None
        self._adaptive_thread: threading.Thread | None = None
        self._stop_adaptive_evt = threading.Event()
        self._adaptive_running = False
        self._adaptive_preset_name = ""
        self._adaptive_preset = None
        self._adaptive_state = None
        self._adaptive_caps: set = set()
        self._adaptive_sample = None
        self._adaptive_applied = ""

        self._dispatch = {
            "ping": self._cmd_ping,
            "apply": self._cmd_apply,
            "apply_loop": self._cmd_apply_loop,
            "stop_loop": self._cmd_stop_loop,
            "status": self._cmd_status,
            "apply_saved": self._cmd_apply_saved,
            "reload_config": self._cmd_reload_config,
            "reset_state": self._cmd_reset_state,
            "adaptive_start": self._cmd_adaptive_start,
            "adaptive_stop": self._cmd_adaptive_stop,
        }

    def run(self, on_ready=None) -> None:
        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            try:
                os.unlink(cfg.ZMQ_SOCKET_PATH)
                log.warning("Removed stale socket: %s", cfg.ZMQ_SOCKET_PATH)
            except OSError as exc:
                log.error("Cannot remove stale socket %s: %s", cfg.ZMQ_SOCKET_PATH, exc)

        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        try:
            sock.bind(cfg.ZMQ_SOCKET_ADDR)
        except zmq.ZMQError as exc:
            log.error("Cannot bind IPC socket %s: %s", cfg.ZMQ_SOCKET_ADDR, exc)
            sock.close()
            ctx.term()
            return

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.chmod(cfg.ZMQ_SOCKET_PATH, 0o666)

        log.info("IPC socket ready: %s", cfg.ZMQ_SOCKET_ADDR)

        self._start_suspend_monitor()

        def _sig_handler(*_):
            log.info("Signal received, shutting down.")
            self._stop_loop()
            self._stop_monitor()
            self._stop_suspend_monitor()
            if os.path.exists(cfg.ZMQ_SOCKET_PATH):
                os.unlink(cfg.ZMQ_SOCKET_PATH)
            sock.close()
            ctx.term()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

        if on_ready is not None:
            try:
                on_ready()
            except Exception as exc:
                log.warning("on_ready callback raised: %s", exc)

        log.info("Daemon ready, waiting for commands.")

        while True:
            try:
                raw = sock.recv_string()
            except zmq.ZMQError as exc:
                log.error("ZMQ recv error: %s. Shutting down.", exc)
                break
            resp = self.handle(raw)
            try:
                sock.send_string(resp)
            except zmq.ZMQError as exc:
                log.error("ZMQ send error: %s", exc)

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.unlink(cfg.ZMQ_SOCKET_PATH)
        sock.close()
        ctx.term()
        self._stop_suspend_monitor()


def _apply_on_start(daemon: PowerDaemon) -> None:
    try:
        state = _load_saved_preset()
    except Exception as exc:
        log.error("Could not restore saved settings at startup: %s", exc)
        return
    if state is None:
        log.warning("No saved preset to restore at startup, skipping.")
        return

    if state.reapply:
        daemon.start_auto_reapply(state)
    elif state.automation:
        on_ac = _on_ac()
        eff_mode, eff_args = daemon._effective_mode_args(
            state.mode, state.args, automation=True, on_ac=on_ac
        )
        daemon._apply_once(eff_args, eff_mode, reason="restoring saved settings at startup")
        daemon._last_logged_mode = eff_mode
        daemon._start_monitor(state.args, state.mode)
    else:
        daemon.apply_preset_state_once(state, reason="restoring saved settings at startup")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not _acquire_daemon_lock():
        log.error("Another daemon instance is already running (lock: %s).", _DAEMON_LOCK_FILE)
        sys.exit(1)

    cfg.load()
    log_level = logging.DEBUG if cfg.is_debug() else logging.INFO
    logging.getLogger().setLevel(log_level)

    log.info("ZenTune daemon v%s", cfg.LOCAL_VERSION)

    if cfg.get("Info", "Type") == "Intel":
        log.warning("Intel CPU detected. SMU control is not supported; presets will not be applied.")

    from zenmaster.smu import ensure_backend, module_version, unavailable_reason, driver_name

    cpu = cfg.get("Info", "CPU")
    fam = cfg.get("Info", "Family")
    arch = cfg.get("Info", "Architecture")
    log.info("CPU: %s, Family: %s, Arch: %s", cpu, fam, arch)

    backend = ensure_backend()
    if backend == "pci":
        log.info("Secure Boot disabled, using PCI direct access backend.")
    elif backend:
        log.info(_smu_ready_message(driver_name(), module_version()))
    else:
        log.error(_smu_unavailable_message(unavailable_reason() or "SMU backend unavailable."))
        log.warning("Running without SMU access; presets will not be applied.")

    daemon = PowerDaemon()

    def _on_ready():
        if cfg.get("Settings", "ApplyOnStart", "0") == "1":
            _apply_on_start(daemon)
        else:
            log.info("ApplyOnStart is disabled, no preset applied at startup.")
        from Assets.daemon.adaptive import ADAPTIVE_SESSION_FILE
        want_adaptive = cfg.get("Settings", "AutoStartAdaptive", "0") == "1"
        resume_adaptive = os.path.exists(ADAPTIVE_SESSION_FILE)
        if want_adaptive or resume_adaptive:
            preset = cfg.get("Adaptive", "preset", "")
            if preset:
                reason = "auto-start is on" if want_adaptive else "it was running before the restart"
                log.info("Starting Adaptive preset '%s' at startup (%s).", preset, reason)
                daemon._cmd_adaptive_start({"preset": preset})
            elif want_adaptive:
                log.info("Auto Start Adaptive is on but no Adaptive preset is saved yet.")

    daemon.run(on_ready=_on_ready)


if __name__ == "__main__":
    main()