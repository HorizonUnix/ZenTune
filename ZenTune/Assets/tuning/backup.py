from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from Assets.core import config as cfg
from Assets.tuning import custom, adaptivepreset

BACKUP_FORMAT = "ZenTune Preset Backup"
BACKUP_VERSION = 1


def export_backup(dest_path: str | Path | None = None) -> tuple[bool, str, int, int]:
    if dest_path is None:
        dest_path = Path.home() / "zentune_backup.json"
    else:
        dest_path = Path(dest_path).expanduser().resolve()

    try:
        custom_presets = custom.load_custom_presets()
        adaptive_presets = adaptivepreset._load()
        payload = {
            "format": BACKUP_FORMAT,
            "version": BACKUP_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "custom_presets": custom_presets,
            "adaptive_presets": adaptive_presets,
        }
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.atomic_write(str(dest_path), json.dumps(payload, indent=2))
        c_count = len(custom_presets)
        a_count = len(adaptive_presets)
        return True, f"Exported {c_count} custom and {a_count} adaptive presets to {dest_path}", c_count, a_count
    except Exception as exc:
        return False, f"Export failed: {exc}", 0, 0


def import_backup(source_path: str | Path, merge: bool = True) -> tuple[bool, str, int, int]:
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.exists():
        return False, f"File not found: {source_path}", 0, 0

    try:
        data = json.loads(source_path.read_text())
    except Exception as exc:
        return False, f"Invalid JSON format: {exc}", 0, 0

    if not isinstance(data, dict) or data.get("format") != BACKUP_FORMAT:
        return False, "Not a valid ZenTune preset backup file", 0, 0

    try:
        incoming_custom = data.get("custom_presets", [])
        incoming_adaptive = data.get("adaptive_presets", {})

        if not isinstance(incoming_custom, list) or not isinstance(incoming_adaptive, dict):
            return False, "Malformed backup contents", 0, 0

        if merge:
            existing_custom = {p.get("name"): p for p in custom.load_custom_presets() if isinstance(p, dict) and p.get("name")}
            for p in incoming_custom:
                if isinstance(p, dict) and p.get("name"):
                    existing_custom[p["name"]] = p
            merged_custom = list(existing_custom.values())

            merged_adaptive = adaptivepreset._load()
            merged_adaptive.update(incoming_adaptive)
        else:
            merged_custom = incoming_custom
            merged_adaptive = incoming_adaptive

        custom.save_custom_presets(merged_custom)
        adaptivepreset._store(merged_adaptive)

        c_count = len(incoming_custom)
        a_count = len(incoming_adaptive)
        return True, f"Imported {c_count} custom and {a_count} adaptive presets from {source_path}", c_count, a_count
    except Exception as exc:
        return False, f"Import failed: {exc}", 0, 0
