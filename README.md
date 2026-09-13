<picture><img align="center" src="/Img/Banner.png"/></picture>
<h4>Powered by ZenMaster and Python</h4>

[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/ZenTune/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/ZenTune/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/ZenTune?style=flat-square)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/HorizonUnix/ZenTune)

## Overview

ZenTune (formerly UXTU4Linux) is a power management tool for **AMD Ryzen APUs and desktop CPUs** on Linux and macOS. Talks to the CPU through direct PCI access on most systems, or through [ryzen_smu](https://github.com/amkillam/ryzen_smu) when Secure Boot is enabled. Set power limits, thermal ceilings, VRM current limits, clocks, and Curve Optimizer offsets without entering firmware setup. The terminal UI runs as an unprivileged user; a root background service manages privileged hardware operations via `run0` or `sudo`.

- Built-in Eco / Balanced / Performance / Extreme presets for Ryzen APUs, desktop CPUs, and Framework Laptops
- Adaptive Mode (Linux only): dynamically scales power limits, Curve Optimizer offsets, and iGPU clocks responding live to temperature and compute load
- Custom Preset Editor with ~65 parameters on APUs: power limits (STAPM/Fast/Slow), thermal targets, VRM currents, per-core Curve Optimizer, and static clocks
- Platform controls: Energy Performance Preference (EPP), CPU Boost toggle, and power profile daemon integration (`power-profiles-daemon`, `TuneD`, or ACPI fallback)
- ASUS hardware controls: thermal performance policies, discrete GPU Eco mode, and MUX isolation on supported laptops
- NVIDIA discrete GPU controls: frequency locks, core clock offsets, memory clock offsets, and power caps via NVML
- Preset Backup and Restore: unified export and import (`~/zentune_backup.json`) across systems
- Live sensor telemetry (Linux): Home tab graphs for CPU temperature, package power, core clock, and workload utilization
- Event-driven automations: automatic preset switching on AC/battery power transitions and post-suspend resume
- Anti-flap protection and reapply loops to prevent OEM thermal managers from overriding active limits
- Status and Hardware tabs: live SMU command execution logs, hardware return codes, and physical CCD topology
- Built-in updater preserving local configuration and custom presets

---

## Compatibility

| Platform | Status |
|----------|--------|
| Linux with systemd, Python 3.10+ | Actively supported (`run0` and `sudo` elevation) |
| Linux without systemd (OpenRC, runit, etc.) | Supported: installer configures dependencies; launch daemon manually |
| macOS (Hackintosh, AMD Ryzen CPU) | Supported: tuning, presets, and automations; Adaptive Mode and Home tab graphs are Linux-only |
| Intel | Not supported |

> [!NOTE]
> **ryzen_smu is only required on Linux when Secure Boot is enabled.** Direct PCI access operates without external kernel modules on standard Linux installations. On macOS, the daemon communicates with the SMU via [DirectHW](https://github.com/joevt/directhw) or the kext-free IOPCIBridge path (`debug=0x144`). Home tab sensor graphs and Adaptive Mode are Linux-exclusive. For full platform setup and troubleshooting details, see the **[Wiki](../../wiki)**.

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/HorizonUnix/ZenTune/main/install.sh | bash
```

Then run:

```bash
zentune
```

The first run walks you through setting up the daemon and detecting your hardware. For the full setup guide, ryzen_smu build steps and troubleshooting, see the **[Wiki](../../wiki)**.

---

## Preview

<p align="left">
  <img src="/Img/home.png"/>
  <img src="/Img/premade.png"/>
  <img src="/Img/custom.png"/>
  <img src="/Img/adaptive.png"/>
  <img src="/Img/auto.png"/>
  <img src="/Img/info.png"/>
  <img src="/Img/status.png"/>
  <img src="/Img/settings.png"/>
</p>

---

## Acknowledgments

| Contributor | Contribution |
|-------------|-------------|
| [FlyGoat](https://github.com/FlyGoat) | [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) |
| [JamesCJ60](https://github.com/JamesCJ60) | [UXTU](https://github.com/JamesCJ60/Universal-x86-Tuning-Utility) preset design and inspiration |
| [amkillam](https://github.com/amkillam) | [ryzen_smu](https://github.com/amkillam/ryzen_smu) DKMS fork |
| [utajum](https://github.com/utajum) | [g-helper-linux](https://github.com/utajum/g-helper-linux) reference for ASUS WMI and power profile support |
| [b00t0x](https://github.com/b00t0x) | Guidance on ryzenadj build dependencies |
| [NotchApple1703](https://github.com/NotchApple1703) | Advisor |