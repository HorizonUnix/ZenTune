from __future__ import annotations

from Assets.core import config as cfg
from Assets.core.powerstate import on_ac


WORDMARK = "◆ ZenTune"

BANNER = r"""
███████╗███████╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗
╚══███╔╝██╔════╝████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝
  ███╔╝ █████╗  ██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗  
 ███╔╝  ██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝  
███████╗███████╗██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗
╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝
""".strip("\n")


def status_line() -> str:
    cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    if cpu and family:
        return f"{cpu} [dim]{family}[/]"
    return cpu


ADAPTIVE_ON_MSG = (
    "Adaptive Mode is running. Stop it in the Adaptive tab to apply a preset manually."
)


async def ensure_sudo(app) -> bool:
    from Assets.daemon.service import sudo_available
    if sudo_available():
        return True
    from Assets.tui.modals import SudoModal
    return bool(await app.push_screen_wait(SudoModal()))


def exclude_adaptive_when_macos(items, key=lambda x: x, excluded="adaptive"):
    from Assets.core import platform as plat
    if not plat.IS_MACOS:
        return items
    filtered = [x for x in items if key(x) != excluded]
    return tuple(filtered) if isinstance(items, tuple) else filtered


SUPPORTED_CPU_TYPES = ("Amd_Apu", "Amd_Desktop_Cpu")


def hardware_info_lines() -> list[str]:
    cpu = cfg.get("Info", "CPU") or "Unknown"
    family = cfg.get("Info", "Family") or "Unknown"
    arch = cfg.get("Info", "Architecture") or "Unknown"
    cpu_type = cfg.get("Info", "Type") or "Unknown"
    lines = [
        f"  CPU           {cpu}",
        f"  Family        {family}",
        f"  Architecture  {arch}",
        f"  Type          {cpu_type}",
        "",
    ]
    if cpu_type in SUPPORTED_CPU_TYPES:
        from Assets.engine.presets import get_preset_label
        variant = cfg.get("Info", "Variant") or ""
        label = get_preset_label(cpu_type, family, cpu, variant)
        lines.append("  [green]Hardware is supported.[/]")
        lines.append(f"  Preset profile  {label}")
    else:
        lines.append("  [yellow]Hardware may not be fully supported.[/]")
        lines.append("  Custom presets are still available.")
    return lines

