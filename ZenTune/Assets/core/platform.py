from __future__ import annotations

import platform as _platform

IS_MACOS = _platform.system() == "Darwin"
IS_LINUX = _platform.system() == "Linux"

RUNTIME_DIR = "/var/run" if IS_MACOS else "/run"
