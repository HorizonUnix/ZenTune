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
EPP_CHOICES = ["Power", "Balance Power", "Balance Performance", "Performance"]
_EPP_VALUES = ["power", "balance_power", "balance_performance", "performance"]
CPU_BOOST_CHOICES = ["Disabled", "Enabled"]
_CPU_BOOST_VALUES = ["0", "1"]
_CPU_BOOST_PATH = "/sys/devices/system/cpu/cpufreq/boost"

_last_written: dict[str, str] = {}
_SETTLE_DELAY_S: float = 0.5


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
    fallbacks: dict[str, list[str]] = {
        "low-power": ["quiet", "silent", "cool", "battery", "powersave", "balanced"],
        "quiet": ["low-power", "silent", "cool", "battery", "powersave", "balanced"],
        "cool": ["quiet", "low-power", "balanced"],
        "balanced": ["balanced-performance", "normal", "default", "performance", "quiet", "low-power"],
        "balanced-performance": ["performance", "balanced"],
        "performance": ["balanced-performance", "turbo", "high-performance", "balanced"],
    }
    for alt in fallbacks.get(canonical, []):
        if alt in available:
            return alt

    canon_clean = canonical.lower().replace("-", "").replace("_", "")
    for choice in available:
        choice_clean = choice.lower().replace("-", "").replace("_", "")
        if canon_clean in choice_clean or choice_clean in canon_clean:
            return choice

    return available[0] if available else None


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


_cached_backend: str | None = None
_cached_backend_time: float = 0.0
_BACKEND_CACHE_TTL: float = 10.0


def is_ppd_active() -> bool:
    ppctl = shutil.which("powerprofilesctl")
    if ppctl:
        try:
            r = subprocess.run([ppctl, "get"], capture_output=True, text=True, timeout=1.5)
            if r.returncode == 0 and bool(r.stdout.strip()):
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    systemctl = shutil.which("systemctl")
    if systemctl:
        try:
            r = subprocess.run(
                [systemctl, "is-active", "--quiet", "power-profiles-daemon"],
                timeout=1.5,
            )
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    busctl = shutil.which("busctl")
    if busctl:
        if is_tuned_active():
            return False
        try:
            r = subprocess.run(
                [busctl, "get-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", "ActiveProfile"],
                capture_output=True, text=True, timeout=1.5,
            )
            if r.returncode == 0 and "s " in r.stdout:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    return False


def is_tuned_active() -> bool:
    tuned = shutil.which("tuned-adm")
    if not tuned:
        return False
    try:
        r = subprocess.run([tuned, "active"], capture_output=True, text=True, timeout=2.0)
        return r.returncode == 0 and "Current active profile:" in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def get_power_profile_backend(force_refresh: bool = False) -> str:
    global _cached_backend, _cached_backend_time
    now = time.monotonic()
    if not force_refresh and _cached_backend is not None and (now - _cached_backend_time) < _BACKEND_CACHE_TTL:
        return _cached_backend

    backend = "none"
    if is_tuned_active():
        backend = "tuned"
    elif is_ppd_active():
        backend = "ppd"
    elif os.path.exists(PLATFORM_PROFILE):
        backend = "sysfs"

    _cached_backend = backend
    _cached_backend_time = now
    return backend


def power_profile_available() -> bool:
    return get_power_profile_backend() != "none"


_BACKEND_DISPLAY_NAMES = {
    "ppd": "power-profiles-daemon",
    "tuned": "TuneD",
    "sysfs": "platform_profile",
}


def power_profile_backend_name() -> str | None:
    return _BACKEND_DISPLAY_NAMES.get(get_power_profile_backend())


def get_current_power_profile() -> str | None:
    backend = get_power_profile_backend()
    if backend == "ppd":
        ppctl = shutil.which("powerprofilesctl")
        if ppctl:
            try:
                r = subprocess.run([ppctl, "get"], capture_output=True, text=True, timeout=1.5)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        busctl = shutil.which("busctl")
        if busctl:
            try:
                r = subprocess.run(
                    [busctl, "get-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", "ActiveProfile"],
                    capture_output=True, text=True, timeout=1.5,
                )
                if r.returncode == 0 and "s " in r.stdout:
                    parts = r.stdout.strip().split('"', 2)
                    if len(parts) >= 2:
                        return parts[1]
            except (OSError, subprocess.TimeoutExpired):
                pass
    elif backend == "tuned":
        tuned = shutil.which("tuned-adm")
        if tuned:
            try:
                r = subprocess.run([tuned, "active"], capture_output=True, text=True, timeout=2.0)
                if r.returncode == 0:
                    for line in r.stdout.splitlines():
                        if "Current active profile:" in line:
                            return line.partition(":")[2].strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
    elif backend == "sysfs":
        return _read(PLATFORM_PROFILE)
    return None


def set_power_profile(index: int) -> str:
    if not 0 <= index < len(POWER_PROFILE_CHOICES):
        return f"power-profile -> invalid value {index}"
    label = POWER_PROFILE_CHOICES[index]

    backend = get_power_profile_backend()

    if backend == "ppd":
        profile = _PPD_PROFILES[index]
        current = get_current_power_profile()
        if current == profile or _last_written.get("ppd") == profile:
            _last_written["ppd"] = profile
            return f"power-profile -> {label} (power-profiles-daemon, unchanged)"

        ppctl = shutil.which("powerprofilesctl")
        if ppctl:
            try:
                r = subprocess.run([ppctl, "set", profile], capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return "power-profile -> powerprofilesctl failed to run"
            if r.returncode == 0:
                _last_written["ppd"] = profile
                time.sleep(_SETTLE_DELAY_S)
                return f"power-profile -> {label} (power-profiles-daemon)"
            if profile == "performance":
                try:
                    r2 = subprocess.run([ppctl, "set", "balanced"], capture_output=True, text=True, timeout=5)
                    if r2.returncode == 0:
                        _last_written["ppd"] = "balanced"
                        time.sleep(_SETTLE_DELAY_S)
                        return f"power-profile -> Balanced (power-profiles-daemon, 'performance' unsupported)"
                except (OSError, subprocess.TimeoutExpired):
                    pass
            return f"power-profile -> power-profiles-daemon rejected: {r.stderr.strip() or 'unknown error'}"

        busctl = shutil.which("busctl")
        if busctl:
            try:
                r = subprocess.run(
                    ["busctl", "set-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", "ActiveProfile", "s", profile],
                    capture_output=True, text=True, timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                return "power-profile -> busctl failed to run"
            if r.returncode == 0:
                _last_written["ppd"] = profile
                time.sleep(_SETTLE_DELAY_S)
                return f"power-profile -> {label} (power-profiles-daemon via busctl)"
            return f"power-profile -> D-Bus rejected: {r.stderr.strip() or 'unknown error'}"

    elif backend == "tuned":
        profile = _TUNED_PROFILES[index]
        current = get_current_power_profile()
        if current == profile or _last_written.get("tuned") == profile:
            _last_written["tuned"] = profile
            return f"power-profile -> {label} (tuned: {profile}, unchanged)"

        tuned = shutil.which("tuned-adm")
        if tuned:
            try:
                r = subprocess.run([tuned, "profile", profile], capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                return "power-profile -> tuned-adm failed to run"
            if r.returncode == 0:
                _last_written["tuned"] = profile
                time.sleep(_SETTLE_DELAY_S)
                return f"power-profile -> {label} (tuned: {profile})"
            return f"power-profile -> tuned rejected: {r.stderr.strip() or 'unknown error'}"

    elif backend == "sysfs":
        profile = resolve_profile(_SYSFS_PROFILES[index], _profile_choices())
        if profile is None:
            return f"power-profile -> '{label}' not supported by this firmware"
        current = _read(PLATFORM_PROFILE)
        if current == profile or _last_written.get(PLATFORM_PROFILE) == profile:
            _last_written[PLATFORM_PROFILE] = profile
            return f"power-profile -> {label} ({profile}, unchanged)"
        if _write(PLATFORM_PROFILE, profile):
            _last_written[PLATFORM_PROFILE] = profile
            time.sleep(_SETTLE_DELAY_S)
            if tlp_profile_conflict():
                return (
                    f"power-profile -> {label} ({profile}) "
                    f"[!] TLP sets PLATFORM_PROFILE_ON_AC/BAT and will override this on "
                    f"power changes. Comment those out in /etc/tlp.conf to let ZenTune manage it"
                )
            return f"power-profile -> {label} ({profile})"
        return f"power-profile -> failed to write {PLATFORM_PROFILE}"

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


def _epp_paths() -> list[str]:
    paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference")
    if not paths:
        paths = glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
    return sorted(paths)


def epp_available() -> bool:
    return len(_epp_paths()) > 0


def set_epp(index: int) -> str:
    if not 0 <= index < len(_EPP_VALUES):
        return f"epp -> invalid value {index}"
    label = EPP_CHOICES[index]
    value = _EPP_VALUES[index]
    paths = _epp_paths()
    if not paths:
        return "epp -> energy_performance_preference not supported on this kernel/CPU"
    if _last_written.get("epp") == value:
        return f"epp -> {label} (unchanged)"
    all_ok = True
    for p in paths:
        if not _write(p, value):
            all_ok = False
    if all_ok:
        _last_written["epp"] = value
        return f"epp -> {label}"
    return f"epp -> failed to write all cores"


def cpu_boost_available() -> bool:
    return os.path.exists(_CPU_BOOST_PATH)


def set_cpu_boost(index: int) -> str:
    if not 0 <= index < len(_CPU_BOOST_VALUES):
        return f"cpu-boost -> invalid value {index}"
    label = CPU_BOOST_CHOICES[index]
    value = _CPU_BOOST_VALUES[index]
    if not os.path.exists(_CPU_BOOST_PATH):
        return "cpu-boost -> cpufreq boost not found"
    if _read(_CPU_BOOST_PATH) == value or _last_written.get(_CPU_BOOST_PATH) == value:
        _last_written[_CPU_BOOST_PATH] = value
        return f"cpu-boost -> {label} (unchanged)"
    if _write(_CPU_BOOST_PATH, value):
        _last_written[_CPU_BOOST_PATH] = value
        return f"cpu-boost -> {label}"
    return f"cpu-boost -> failed to write {_CPU_BOOST_PATH}"