from __future__ import annotations

import glob
import os
import shutil
import subprocess
import time

PLATFORM_PROFILE = "/sys/firmware/acpi/platform_profile"
PLATFORM_PROFILE_CHOICES = "/sys/firmware/acpi/platform_profile_choices"

_ASUS_TTP_PATHS = (
    "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy",
    "/sys/bus/platform/devices/asus-nb-wmi/throttle_thermal_policy",
    "/sys/class/firmware-attributes/asus-armoury/attributes/throttle_thermal_policy/current_value",
)

_ASUS_DGPU_PATHS = (
    "/sys/devices/platform/asus-nb-wmi/dgpu_disable",
    "/sys/bus/platform/devices/asus-nb-wmi/dgpu_disable",
    "/sys/class/firmware-attributes/asus-armoury/attributes/dgpu_disable/current_value",
)

_ASUS_MUX_PATHS = (
    "/sys/devices/platform/asus-nb-wmi/gpu_mux_mode",
    "/sys/bus/platform/devices/asus-nb-wmi/gpu_mux_mode",
    "/sys/class/firmware-attributes/asus-armoury/attributes/gpu_mux_mode/current_value",
)

POWER_PROFILE_CHOICES = ["Power Saver", "Balanced", "Performance"]
_SYSFS_PROFILES = ["low-power", "balanced", "performance"]
_PPD_PROFILES = ["power-saver", "balanced", "performance"]
_TUNED_PROFILES = ["powersave", "balanced", "throughput-performance"]

ASUS_MODE_CHOICES = ["Silent", "Balanced", "Turbo"]
_ASUS_TTP_VALUES = [2, 0, 1]

ASUS_ECO_CHOICES = ["dGPU On", "dGPU Off (Eco)"]
ASUS_MUX_CHOICES = ["dGPU (Ultimate)", "Optimus (Hybrid)"]
CCD_AFFINITY_CHOICES = ["All Cores", "CCD1 Only", "CCD2 Only"]

_last_written: dict[str, str] = {}


def _read(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _write(path: str, value: str) -> bool:
    try:
        with open(path, "w") as f:
            f.write(value)
        return True
    except OSError:
        return False


def resolve_profile(canonical: str, available: list[str]) -> str | None:
    if not available:
        return canonical
    if canonical in available:
        return canonical
    synonyms = {
        "low-power": ["quiet", "balanced"],
        "quiet": ["low-power"],
        "balanced": ["balanced-performance"],
        "balanced-performance": ["balanced"],
        "performance": ["balanced"],
    }
    for alt in synonyms.get(canonical, []):
        if alt in available:
            return alt
    return None


def _profile_choices() -> list[str]:
    raw = _read(PLATFORM_PROFILE_CHOICES)
    return raw.split() if raw else []


_tlp_conflict: bool | None = None


def tlp_profile_conflict() -> bool:
    global _tlp_conflict
    if _tlp_conflict is not None:
        return _tlp_conflict
    _tlp_conflict = False
    if shutil.which("tlp") is not None:
        for path in ["/etc/tlp.conf", *sorted(glob.glob("/etc/tlp.d/*.conf"))]:
            try:
                with open(path) as f:
                    if any(line.lstrip().startswith("PLATFORM_PROFILE_ON_") for line in f):
                        _tlp_conflict = True
                        break
            except OSError:
                continue
    return _tlp_conflict


def power_profile_available() -> bool:
    return (
        os.path.exists(PLATFORM_PROFILE)
        or shutil.which("powerprofilesctl") is not None
        or shutil.which("tuned-adm") is not None
    )


def set_power_profile(index: int) -> str:
    if not 0 <= index < len(_SYSFS_PROFILES):
        return f"power-profile -> invalid value {index}"
    label = POWER_PROFILE_CHOICES[index]

    if os.path.exists(PLATFORM_PROFILE):
        profile = resolve_profile(_SYSFS_PROFILES[index], _profile_choices())
        if profile is None:
            return f"power-profile -> '{label}' not supported by this firmware"
        if _last_written.get(PLATFORM_PROFILE) == profile:
            return f"power-profile -> {label} ({profile}, unchanged)"
        if _write(PLATFORM_PROFILE, profile):
            _last_written[PLATFORM_PROFILE] = profile
            if tlp_profile_conflict():
                return (
                    f"power-profile -> {label} ({profile}) "
                    f"[!] TLP sets PLATFORM_PROFILE_ON_AC/BAT and will override this on "
                    f"power changes. Comment those out in /etc/tlp.conf to let ZenTune manage it"
                )
            return f"power-profile -> {label} ({profile})"
        return f"power-profile -> failed to write {PLATFORM_PROFILE}"

    ppctl = shutil.which("powerprofilesctl")
    if ppctl:
        profile = _PPD_PROFILES[index]
        if _last_written.get("ppd") == profile:
            return f"power-profile -> {label} (unchanged)"
        try:
            r = subprocess.run([ppctl, "set", profile], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return "power-profile -> powerprofilesctl failed to run"
        if r.returncode == 0:
            _last_written["ppd"] = profile
            return f"power-profile -> {label} (power-profiles-daemon)"
        return f"power-profile -> rejected: {r.stderr.strip() or 'unknown error'}"

    tuned = shutil.which("tuned-adm")
    if tuned:
        profile = _TUNED_PROFILES[index]
        if _last_written.get("tuned") == profile:
            return f"power-profile -> {label} (unchanged)"
        try:
            r = subprocess.run([tuned, "profile", profile], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return "power-profile -> tuned-adm failed to run"
        if r.returncode == 0:
            _last_written["tuned"] = profile
            return f"power-profile -> {label} (tuned: {profile})"
        return f"power-profile -> tuned rejected: {r.stderr.strip() or 'unknown error'}"

    return "power-profile -> no platform_profile, power-profiles-daemon, or tuned on this system"


def _asus_ttp_path() -> str | None:
    for path in _ASUS_TTP_PATHS:
        if os.path.exists(path):
            return path
    return None


def asus_available() -> bool:
    return _asus_ttp_path() is not None


def set_asus_mode(index: int) -> str:
    if not 0 <= index < len(_ASUS_TTP_VALUES):
        return f"asus-mode -> invalid value {index}"
    label = ASUS_MODE_CHOICES[index]

    path = _asus_ttp_path()
    if path is None:
        return "asus-mode -> asus-wmi throttle_thermal_policy not found (not an ASUS laptop?)"

    value = str(_ASUS_TTP_VALUES[index])
    if _last_written.get(path) == value:
        return f"asus-mode -> {label} (unchanged)"
    if _write(path, value):
        _last_written[path] = value
        return f"asus-mode -> {label}"
    return f"asus-mode -> failed to write {path}"


def _first_path(paths: tuple[str, ...]) -> str | None:
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def _read_int(path: str | None) -> int:
    raw = _read(path) if path else None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _nvidia_drm_active() -> bool:
    if not os.path.isdir("/sys/module/nvidia_drm"):
        return False
    refcnt = _read("/sys/module/nvidia_drm/refcnt")
    try:
        return int(refcnt) > 0
    except (TypeError, ValueError):
        return True


def _amd_dgpu_active() -> bool:
    if not os.path.isdir("/sys/module/amdgpu"):
        return False
    pci = "/sys/bus/pci/devices"
    try:
        devices = os.listdir(pci)
    except OSError:
        return False
    for dev in devices:
        base = os.path.join(pci, dev)
        if _read(os.path.join(base, "vendor")) != "0x1002":
            continue
        cls = _read(os.path.join(base, "class")) or ""
        if not (cls.startswith("0x0300") or cls.startswith("0x0302")):
            continue
        if _read(os.path.join(base, "boot_vga")) == "1":
            continue
        driver = os.path.join(base, "driver")
        if not os.path.islink(driver) or os.path.basename(os.path.realpath(driver)) != "amdgpu":
            continue
        return _read(os.path.join(base, "power", "runtime_status")) != "suspended"
    return False


def asus_eco_available() -> bool:
    return _first_path(_ASUS_DGPU_PATHS) is not None


def set_asus_eco(index: int) -> str:
    if not 0 <= index < len(ASUS_ECO_CHOICES):
        return f"asus-eco -> invalid value {index}"
    label = ASUS_ECO_CHOICES[index]

    path = _first_path(_ASUS_DGPU_PATHS)
    if path is None:
        return "asus-eco -> dgpu_disable not found (no ASUS dGPU control on this machine)"

    if _read_int(path) == index:
        return f"asus-eco -> {label} (unchanged)"

    if index == 1:
        if _nvidia_drm_active() or _amd_dgpu_active():
            return (
                "asus-eco -> refused: the dGPU driver is active. Disabling the dGPU now "
                "would hot-remove it and can crash the kernel. Close everything using "
                "the dGPU first."
            )
        if _read_int(_first_path(_ASUS_MUX_PATHS)) == 0:
            return (
                "asus-eco -> refused: GPU MUX is in dGPU (Ultimate) mode. The dGPU is the "
                "only display output; disabling it would black-screen the system."
            )

    if not _write(path, str(index)):
        return f"asus-eco -> failed to write {path}"

    if index == 0:
        time.sleep(0.05)
        _write("/sys/bus/pci/rescan", "1")
    return f"asus-eco -> {label}"


def asus_mux_available() -> bool:
    return _first_path(_ASUS_MUX_PATHS) is not None


def set_asus_mux(index: int) -> str:
    if not 0 <= index < len(ASUS_MUX_CHOICES):
        return f"asus-mux -> invalid value {index}"
    label = ASUS_MUX_CHOICES[index]

    path = _first_path(_ASUS_MUX_PATHS)
    if path is None:
        return "asus-mux -> gpu_mux_mode not found (no MUX switch on this machine)"

    if _read_int(path) == index:
        return f"asus-mux -> {label} (unchanged)"

    if _read_int(_first_path(_ASUS_DGPU_PATHS)) == 1:
        return (
            "asus-mux -> refused: the dGPU is disabled (Eco). The firmware rejects MUX "
            "changes while the dGPU is powered off. Switch GPU Eco to 'dGPU On' first."
        )

    if not _write(path, str(index)):
        return f"asus-mux -> failed to write {path} (firmware may have rejected it)"
    return f"asus-mux -> {label} [!] reboot required to take effect"


def _l3_domains() -> list[str]:
    domains: list[str] = []
    cpu_root = "/sys/devices/system/cpu"
    try:
        cpus = sorted(
            (d for d in os.listdir(cpu_root) if d.startswith("cpu") and d[3:].isdigit()),
            key=lambda d: int(d[3:]),
        )
    except OSError:
        return domains
    for cpu in cpus:
        shared = _read(os.path.join(cpu_root, cpu, "cache", "index3", "shared_cpu_list"))
        if shared and shared not in domains:
            domains.append(shared)
    return domains


def ccd_affinity_available() -> bool:
    return len(_l3_domains()) >= 2 and shutil.which("systemctl") is not None


def set_ccd_affinity(index: int) -> str:
    if not 0 <= index < len(CCD_AFFINITY_CHOICES):
        return f"ccd-affinity -> invalid value {index}"
    label = CCD_AFFINITY_CHOICES[index]

    if index == 0:
        cpus = _read("/sys/devices/system/cpu/present") or "0"
    else:
        domains = _l3_domains()
        if len(domains) < index:
            return f"ccd-affinity -> CCD{index} not found (single-CCD CPU?)"
        cpus = domains[index - 1]

    if _last_written.get("ccd") == cpus:
        return f"ccd-affinity -> {label} (unchanged)"
    try:
        r = subprocess.run(
            ["systemctl", "set-property", "--runtime", "user.slice", f"AllowedCPUs={cpus}"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "ccd-affinity -> systemctl failed to run"
    if r.returncode != 0:
        return f"ccd-affinity -> rejected: {r.stderr.strip() or 'unknown error'}"
    _last_written["ccd"] = cpus
    return f"ccd-affinity -> {label} (user applications pinned to CPUs {cpus})"