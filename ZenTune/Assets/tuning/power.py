from __future__ import annotations

from Assets.core import config as cfg


def _strip_cpu_name(raw: str) -> str:
    for word in ("AMD", "with", "Mobile", "Ryzen", "Radeon", "Graphics", "Vega", "Gfx"):
        raw = raw.replace(word, "")
    return raw


def current_preset_label() -> str:
    from Assets.engine.presets import get_preset_label

    raw_cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    cpu_type = cfg.get("Info", "Type")
    variant = cfg.get("Info", "Variant")
    cpu_model = _strip_cpu_name(raw_cpu)
    return get_preset_label(cpu_type, family, cpu_model, variant)


def get_presets() -> dict:
    from Assets.engine.presets import get_preset, to_dict

    raw_cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    cpu_type = cfg.get("Info", "Type")
    variant = cfg.get("Info", "Variant")
    cpu_model = _strip_cpu_name(raw_cpu)

    preset = get_preset(cpu_type, family, cpu_model, variant)
    cfg.set_loaded_preset(current_preset_label())
    return to_dict(preset)


def apply_preset(args: str, mode: str) -> dict:
    from Assets.core.ipc import get_client

    if cfg.get("Info", "Type") == "Intel":
        return {"ok": False, "error": "Intel chipsets are not supported."}

    cfg.set_config("User", "Mode", mode)
    cfg.save()

    client = get_client()
    if not client.ping():
        return {"ok": False, "error": "Daemon is not running."}

    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    automation = bool(cfg.get("Automations", "OnAC", "") or cfg.get("Automations", "OnBattery", ""))
    reapply = cfg.get("Settings", "ReApply", "0") == "1"

    if reapply:
        return client.apply_loop(args=args, mode=mode, interval=interval, automation=automation)
    return client.apply(args=args, mode=mode)


def update_reapply_interval(val: str) -> bool:
    if not val.isdigit():
        return False
    clamped = str(cfg.parse_interval(val, default=3))
    cfg.set_config("Settings", "Time", clamped)
    cfg.save()
    from Assets.core.ipc import get_client
    client = get_client()
    if client.ping():
        client.apply_saved()
    return True
