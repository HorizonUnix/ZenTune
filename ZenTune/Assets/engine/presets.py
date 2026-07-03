from __future__ import annotations

from dataclasses import dataclass, asdict


RYZEN_FAMILY = [
    "Unknown", "SummitRidge", "PinnacleRidge", "RavenRidge", "Dali", "Pollock",
    "Picasso", "FireFlight", "Matisse", "Renoir", "Lucienne", "VanGogh",
    "Mendocino", "Vermeer", "Cezanne_Barcelo", "Rembrandt", "Raphael",
    "DragonRange", "PhoenixPoint", "PhoenixPoint2", "HawkPoint", "HawkPoint2",
    "SonomaValley", "GraniteRidge", "FireRange", "StrixHalo", "StrixPoint",
    "KrackanPoint", "KrackanPoint2",
]


@dataclass
class Preset:
    Eco: str
    Balance: str
    Performance: str
    Extreme: str


def to_dict(preset: Preset) -> dict:
    return {k: v for k, v in asdict(preset).items() if v is not None}


def _family_idx(name: str) -> int:
    try:
        return RYZEN_FAMILY.index(name)
    except ValueError:
        return -1


def _before(family: str, ref: str) -> bool:
    return _family_idx(family) < _family_idx(ref)


def get_preset(cpu_type: str, family: str, cpu_model: str, variant: str = "") -> Preset:
    if variant:
        preset = _variant_preset(variant)
        if preset is not None:
            return preset
    if cpu_type == "Amd_Apu":
        return _apu_preset(family, cpu_model)
    if cpu_type == "Amd_Desktop_Cpu":
        return _desktop_preset(family, cpu_model)
    return _desktop_standard()


def get_preset_label(cpu_type: str, family: str, cpu_model: str, variant: str = "") -> str:
    if variant and _variant_preset(variant) is not None:
        return variant
    if cpu_type == "Amd_Apu":
        return _apu_label(family, cpu_model)
    if cpu_type == "Amd_Desktop_Cpu":
        return _desktop_label(family, cpu_model)
    return family or "Unknown"


def _variant_preset(variant: str) -> Preset | None:
    match variant:
        case "AMDFrameworkLaptop16Ryzen7040_RX7700S":
            return Preset(
                Eco="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=45 --stapm-limit=30000 --fast-limit=35000 --slow-limit=30000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=0",
                Balance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=95000 --fast-limit=95000 --slow-limit=95000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=1",
                Performance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=100000 --fast-limit=100000 --slow-limit=120000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=2",
                Extreme="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=120000 --fast-limit=140000 --slow-limit=120000 --vrm-current=200000 --vrmmax-current=200000 --vrmsoc-current=200000 --vrmsocmax-current=200000 --sys-power-profile=2",
            )
        case "AMDFrameworkLaptop16Ryzen7040":
            return Preset(
                Eco="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --slow-limit=6000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=0",
                Balance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=35000 --fast-limit=45000 --slow-limit=38000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=1",
                Performance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=45000 --fast-limit=55000 --slow-limit=50000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=2",
                Extreme="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=55000 --fast-limit=70000 --slow-limit=65000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=2",
            )
        case "AMDFrameworkLaptop13Ryzen7040_RyzenAI300":
            return Preset(
                Eco="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=45 --stapm-limit=8000 --fast-limit=10000 --slow-limit=8000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=0",
                Balance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=15000 --fast-limit=18000 --slow-limit=15000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=1",
                Performance="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=28000 --fast-limit=42000 --slow-limit=28000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=2",
                Extreme="--tctl-temp=100 --chtc-temp=100 --apu-skin-temp=50 --stapm-limit=35000 --fast-limit=60000 --slow-limit=35000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --sys-power-profile=2",
            )
    return None


def _apu_preset(family: str, cpu_model: str) -> Preset:
    if family in ("DragonRange", "FireRange"):
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --stapm-limit=35000 --fast-limit=45000 --stapm-time=64 --slow-limit=35000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --stapm-limit=100000 --fast-limit=120000 --stapm-time=64 --slow-limit=100000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --stapm-limit=125000 --fast-limit=145000 --stapm-time=64 --slow-limit=125000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000",
        )

    if family == "StrixHalo":
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --stapm-limit=18000 --fast-limit=25000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=55000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --stapm-limit=100000 --fast-limit=120000 --stapm-time=64 --slow-limit=100000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --stapm-limit=145000 --fast-limit=165000 --stapm-time=64 --slow-limit=145000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000",
        )

    if _before(family, "Matisse"):
        return _pre_matisse_apu(cpu_model)

    if family == "Mendocino" and "U" in cpu_model:
        return _apu_u_e_ce()

    return _post_matisse_apu(cpu_model)


def _apu_u_e_ce() -> Preset:
    return Preset(
        Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=16000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=18000 --fast-limit=20000 --stapm-time=64 --slow-limit=19000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=28000 --fast-limit=28000 --stapm-time=64 --slow-limit=28000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
    )


def _pre_matisse_apu(cpu_model: str) -> Preset:
    if any(s in cpu_model for s in ("U", "e", "Ce")):
        return _apu_u_e_ce()

    if "H" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=30000 --fast-limit=35000 --stapm-time=64 --slow-limit=33000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=35000 --fast-limit=42000 --stapm-time=64 --slow-limit=40000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=56000 --fast-limit=56000 --stapm-time=64 --slow-limit=56000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "GE" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=15000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "G" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=80000 --fast-limit=75000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    return _desktop_standard()


def _post_matisse_apu(cpu_model: str) -> Preset:
    if "U" in cpu_model or ("AI" in cpu_model and "HX" not in cpu_model):
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=22000 --fast-limit=24000 --stapm-time=64 --slow-limit=22000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=28000 --fast-limit=28000 --stapm-time=64 --slow-limit=28000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=30000 --fast-limit=34000 --stapm-time=64 --slow-limit=32000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "HX" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=55000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=78000 --fast-limit=70000 --stapm-time=64 --slow-limit=70000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "HS" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=35000 --fast-limit=45000 --stapm-time=64 --slow-limit=38000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=50000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=70000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "H" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "GE" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=15000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    if "G" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Balance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=45 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Performance="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=80000 --fast-limit=75000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
            Extreme="--tctl-temp=95 --chtc-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000",
        )

    return _desktop_standard()


def _desktop_preset(family: str, cpu_model: str) -> Preset:
    parts = cpu_model.split()
    model = parts[1] if len(parts) >= 2 else (parts[0] if parts else "")
    series = parts[0] if len(parts) >= 2 else ""
    pre_raphael = _before(family, "Raphael")

    if "X3D" in model:
        return _dt_x3d()
    if "E" in model:
        return _dt_e()
    if "X" in model and "9" in series:
        return _dt_x9(pre_raphael)
    if "X" in model:
        return _dt_x()
    return _dt_default()


def _dt_e() -> Preset:
    return Preset(
        Eco="--tctl-temp=95 --ppt-limit=45000 --edc-limit=90000 --tdc-limit=90000",
        Balance="--tctl-temp=95 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
        Performance="--tctl-temp=95 --ppt-limit=95000 --edc-limit=122000 --tdc-limit=122000",
        Extreme="--tctl-temp=95 --ppt-limit=105000 --edc-limit=142000 --tdc-limit=142000",
    )


def _dt_x3d() -> Preset:
    return Preset(
        Eco="--tctl-temp=85 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
        Balance="--tctl-temp=85 --ppt-limit=85000 --edc-limit=120000 --tdc-limit=120000",
        Performance="--tctl-temp=85 --ppt-limit=105000 --edc-limit=142000 --tdc-limit=142000",
        Extreme="--tctl-temp=85 --ppt-limit=140000 --edc-limit=190000 --tdc-limit=190000",
    )


def _dt_x9(pre_raphael: bool) -> Preset:
    if pre_raphael:
        return Preset(
            Eco="--tctl-temp=95 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
            Balance="--tctl-temp=95 --ppt-limit=95000 --edc-limit=130000 --tdc-limit=130000",
            Performance="--tctl-temp=95 --ppt-limit=125000 --edc-limit=142000 --tdc-limit=142000",
            Extreme="--tctl-temp=95 --ppt-limit=170000 --edc-limit=230000 --tdc-limit=230000",
        )
    return Preset(
        Eco="--tctl-temp=95 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
        Balance="--tctl-temp=95 --ppt-limit=105000 --edc-limit=145000 --tdc-limit=145000",
        Performance="--tctl-temp=95 --ppt-limit=145000 --edc-limit=210000 --tdc-limit=210000",
        Extreme="--tctl-temp=95 --ppt-limit=230000 --edc-limit=310000 --tdc-limit=310000",
    )


def _dt_x() -> Preset:
    return Preset(
        Eco="--tctl-temp=95 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
        Balance="--tctl-temp=95 --ppt-limit=88000 --edc-limit=125000 --tdc-limit=125000",
        Performance="--tctl-temp=95 --ppt-limit=105000 --edc-limit=142000 --tdc-limit=142000",
        Extreme="--tctl-temp=95 --ppt-limit=140000 --edc-limit=190000 --tdc-limit=190000",
    )


def _dt_default() -> Preset:
    return Preset(
        Eco="--tctl-temp=95 --ppt-limit=45000 --edc-limit=90000 --tdc-limit=90000",
        Balance="--tctl-temp=95 --ppt-limit=65000 --edc-limit=90000 --tdc-limit=90000",
        Performance="--tctl-temp=95 --ppt-limit=88000 --edc-limit=125000 --tdc-limit=125000",
        Extreme="--tctl-temp=95 --ppt-limit=105000 --edc-limit=142000 --tdc-limit=142000",
    )


def _desktop_standard() -> Preset:
    return Preset(
        Eco="--tctl-temp=95", Balance="--tctl-temp=95",
        Performance="--tctl-temp=95", Extreme="--tctl-temp=95",
    )


def _socket(family: str) -> str:
    from zenmaster.runner import get_socket
    return get_socket(family) or ""


def _apu_label(family: str, cpu_model: str) -> str:
    socket = _socket(family)
    if family == "DragonRange":
        return f"AMDAPUDragonRange_{socket}"
    if family == "FireRange":
        return f"AMDAPUFireRange_{socket}"
    if family == "StrixHalo":
        return f"AMDAPUStrixHalo_{socket}"
    if _before(family, "Matisse"):
        return _pre_matisse_label(family, cpu_model)
    if family == "Mendocino" and "U" in cpu_model:
        return f"AMDAPUMendocino_{socket}_U"
    return _post_matisse_label(family, cpu_model)


def _pre_matisse_label(family: str, cpu_model: str) -> str:
    socket = _socket(family)
    if any(s in cpu_model for s in ("U", "e", "Ce")):
        return f"AMDAPUPreMatisse_{socket}_U"
    if "H" in cpu_model:
        return f"AMDAPUPreMatisse_{socket}_H"
    if "GE" in cpu_model:
        return f"AMDAPUPreMatisse_{socket}_GE"
    if "G" in cpu_model:
        return f"AMDAPUPreMatisse_{socket}_G"
    return f"AMDAPUPreMatisse_{socket}"


def _post_matisse_label(family: str, cpu_model: str) -> str:
    socket = _socket(family)
    if "U" in cpu_model or ("AI" in cpu_model and "HX" not in cpu_model):
        return f"AMDAPUPostMatisse_{socket}_U"
    if "HX" in cpu_model:
        return f"AMDAPUPostMatisse_{socket}_HX"
    if "HS" in cpu_model:
        return f"AMDAPUPostMatisse_{socket}_HS"
    if "H" in cpu_model:
        return f"AMDAPUPostMatisse_{socket}_H"
    if "GE" in cpu_model:
        return f"AMDAPUPostMatisse_{socket}_GE"
    if "G" in cpu_model:
        return f"AMDAPUPostMatisse_{socket}_G"
    return f"AMDAPUPostMatisse_{socket}"


def _desktop_label(family: str, cpu_model: str) -> str:
    parts = cpu_model.split()
    model = next((p for p in reversed(parts) if any(c.isdigit() for c in p)), parts[-1] if parts else "")
    series = parts[0] if parts else ""
    socket = _socket(family)
    era = "PreRaphael" if _before(family, "Raphael") else "PostRaphael"
    if "X3D" in model:
        return f"AMDCPU{era}_{socket}_X3D"
    if "E" in model:
        return f"AMDCPU{era}_{socket}_E"
    if "X" in model and "9" in series:
        return f"AMDCPU{era}_{socket}_X9"
    if "X" in model:
        return f"AMDCPU{era}_{socket}_X"
    return f"AMDCPU{era}_{socket}"