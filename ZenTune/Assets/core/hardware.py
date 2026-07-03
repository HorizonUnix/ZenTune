from __future__ import annotations

import os, subprocess

from Assets.core import config as cfg
from Assets.core import platform as plat
from zenmaster.smu import secure_boot_enabled


PROC_CPUINFO = "/proc/cpuinfo"
SYS_CPUFREQ_MAX = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
SYS_DMI_ID_DIR = "/sys/class/dmi/id"


def _cpuinfo_dict() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        with open(PROC_CPUINFO) as f:
            for line in f:
                if ":" not in line:
                    if line.strip() == "" and result:
                        break
                    continue
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
    except OSError:
        pass
    return result


def max_clock_mhz() -> int:
    if plat.IS_MACOS:
        hz = _sysctl_int("hw.cpufrequency_max")
        if hz <= 0:
            return 0
        mhz = hz // 1_000_000
        return ((mhz + 499) // 500) * 500
    try:
        with open(SYS_CPUFREQ_MAX) as f:
            khz = int(f.read().strip())
        return ((khz // 1000 + 499) // 500) * 500
    except (OSError, ValueError):
        pass
    try:
        mhz = float(_cpuinfo_dict().get("cpu MHz", "0"))
    except ValueError:
        mhz = 0
    if mhz <= 0:
        return 0
    return ((int(mhz) + 499) // 500) * 500


_SMU_INSTALL_GUIDE = f"Install guide: {cfg.RYZEN_SMU_WIKI_URL}"


def check_ryzen_smu() -> str | None:
    if not secure_boot_enabled():
        return None

    from zenmaster.smu import module_status

    st = module_status()
    if st.ok:
        return None

    if st.reason == "unknown":
        message = (
            f"ryzen_smu is loaded but its version cannot be determined "
            f"(minimum required: {st.min_version})"
        )
    elif st.reason == "too_old":
        message = f"ryzen_smu version {st.version} is too old (minimum required: {st.min_version})"
    elif st.reason == "not_installed":
        message = "ryzen_smu kernel module is not installed"
    elif st.reason == "unsigned":
        message = "ryzen_smu is installed but not signed for Secure Boot"
    else:
        message = "ryzen_smu is installed but not loaded"

    return f"{message}.\n\n{_SMU_INSTALL_GUIDE}"


def _read_sysfs(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _parse_device_info() -> dict[str, str]:
    return {
        "name": _read_sysfs(os.path.join(SYS_DMI_ID_DIR, "product_name")) or "N/A",
        "producer": _read_sysfs(os.path.join(SYS_DMI_ID_DIR, "sys_vendor")) or "N/A",
        "model": _read_sysfs(os.path.join(SYS_DMI_ID_DIR, "board_name")) or "N/A",
    }


def _lspci_vga() -> str:
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l for l in result.stdout.splitlines() if "VGA" in l or "Display" in l]
        return "\n".join(lines).lower()
    except Exception:
        return ""


def _has_discrete_rx7700s() -> bool:
    vga = _lspci_vga()
    return "7700s" in vga or "rx 7700s" in vga


def _sysctl_int(name: str) -> int:
    try:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return 0
    try:
        return int(out.stdout.strip())
    except ValueError:
        return 0


def _detect_framework_variant() -> str:
    product = (_read_sysfs(os.path.join(SYS_DMI_ID_DIR, "product_name")) or "").lower()
    mfr = (_read_sysfs(os.path.join(SYS_DMI_ID_DIR, "sys_vendor")) or "").lower()

    if "framework" not in mfr:
        return ""

    if "laptop 16" in product and "7040" in product:
        if _has_discrete_rx7700s():
            return "AMDFrameworkLaptop16Ryzen7040_RX7700S"
        return "AMDFrameworkLaptop16Ryzen7040"

    if "laptop 13" in product and ("7040" in product or "ai 300" in product or "ryzen ai 300" in product):
        return "AMDFrameworkLaptop13Ryzen7040_RyzenAI300"

    return ""


_detected_family_cache: str | None = None


def detected_family() -> str:
    global _detected_family_cache
    if _detected_family_cache is None:
        from zenmaster.hardware import detect as zm_detect
        _detected_family_cache = zm_detect().family
    return _detected_family_cache


def detect() -> None:
    from zenmaster.hardware import detect as zm_detect
    info = zm_detect()
    cfg.set_config("Info", "CPU", info.name or "Unknown")
    cfg.set_config("Info", "Signature",
                   f"Family {info.cpu_family_int}, Model {info.cpu_model_int}, Stepping {info.cpu_stepping_int}")
    _compute_codename(info)

    variant = _detect_framework_variant()
    cfg.set_config("Info", "Variant", variant)

    cfg.save()


def _compute_codename(info=None) -> None:
    if info is None:
        raw_cpu = cfg.get("Info", "CPU")
        signature = cfg.get("Info", "Signature")
        try:
            words = signature.split()
            cpu_family = int(words[words.index("Family") + 1].rstrip(","))
            cpu_model = int(words[words.index("Model") + 1].rstrip(","))
        except (ValueError, IndexError):
            cfg.set_config("Info", "Architecture", "Unknown")
            cfg.set_config("Info", "Family", "Unknown")
            cfg.set_config("Info", "Type", "Unknown")
            return
        from zenmaster.hardware import resolve
        info = resolve(raw_cpu, cpu_family, cpu_model)

    from zenmaster.runner import is_supported
    cpu_type = info.type
    if cpu_type in ("Amd_Apu", "Amd_Desktop_Cpu") and not is_supported(info.family):
        cpu_type = "Unknown"
    cfg.set_config("Info", "Architecture", info.arch)
    cfg.set_config("Info", "Family", info.family)
    cfg.set_config("Info", "Type", cpu_type)