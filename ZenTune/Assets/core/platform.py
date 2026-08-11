from __future__ import annotations

from platform import system as _plat_system

IS_MACOS = _plat_system() == "Darwin"
IS_LINUX = _plat_system() == "Linux"

RUNTIME_DIR = "/var/run" if IS_MACOS else "/run"
