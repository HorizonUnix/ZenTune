from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields

from Assets.core import config as cfg

ADAPTIVE_PRESETS_PATH = cfg.ADAPTIVE_PRESETS_PATH


@dataclass
class AdaptivePreset:
    max_temp: int = 85
    power: int = 28
    co_max: int = 30
    igpu_min: int = 400
    igpu_max: int = 2000
    min_cpu_clk: int = 1200
    enable_co: bool = False
    enable_igpu: bool = False
    enable_asus: bool = False
    asus_mode: int = 1
    enable_nvidia: bool = False
    nv_max_clk: int = 4000
    nv_core_offset: int = 0
    nv_mem_offset: int = 0
    nv_power_limit: int = 0


def _load():
    try:
        with open(ADAPTIVE_PRESETS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _store(data):
    cfg.atomic_write(ADAPTIVE_PRESETS_PATH, json.dumps(data, indent=2))


def names():
    return list(_load().keys())


def get(name):
    raw = _load().get(name)
    if raw is None:
        return None
    known = {f.name for f in fields(AdaptivePreset)}
    return AdaptivePreset(**{k: v for k, v in raw.items() if k in known})


def save(name, preset):
    data = _load()
    data[name] = asdict(preset)
    _store(data)


def delete(name):
    data = _load()
    if name in data:
        del data[name]
        _store(data)
