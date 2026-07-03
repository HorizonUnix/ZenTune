#!/usr/bin/env python3
import atexit, os, sys

_ROOT = os.path.dirname(os.path.realpath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import fcntl as _fcntl
from Assets.core import config as cfg
from Assets.flows.setup import (
    check_integrity, check_python_deps, init_config, needs_setup, ensure_custom_presets_file,
)


cfg.load()
_TUI_LOCK_FILE = f"/tmp/{cfg.APP_NAME}_tui.lock"


def _acquire_single_instance() -> bool:
    lock_fh = None
    try:
        lock_fh = open(_TUI_LOCK_FILE, "w")
        _fcntl.flock(lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        lock_fh.write(str(os.getpid()))
        lock_fh.flush()
        atexit.register(lock_fh.close)
        return True
    except (IOError, OSError):
        if lock_fh is not None:
            lock_fh.close()
        return False


def main() -> None:
    if not _acquire_single_instance():
        from Assets.tui.app import run as run_textual
        run_textual(dep_error="ZenTune is already running.\n\nClose the other instance first.")
        sys.exit(1)

    ensure_custom_presets_file()
    dep_error = check_python_deps()

    first_run = needs_setup()
    if first_run:
        init_config()
    else:
        check_integrity()
    cfg.load()

    from Assets.tui.app import run as run_textual
    result = run_textual(first_run=first_run, dep_error=dep_error)
    if result in ("setup-done", "relaunch"):
        os.execv(sys.executable, [sys.executable, *sys.argv])
    elif result == "reset":
        from Assets.flows.setup import reset_all
        try:
            from Assets.core.ipc import get_client
            client = get_client()
            if client.ping():
                client.reset_state()
        except Exception:
            pass
        reset_all()
        os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.stderr.write(f"\n  Error: {exc}\n")
        sys.exit(1)