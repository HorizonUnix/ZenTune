<picture><img align="center" src="/Img/Banner.png"/></picture>
<h4>Powered by ZenMaster and Python</h4>

[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/ZenTune/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/ZenTune/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/ZenTune?style=flat-square)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/HorizonUnix/ZenTune)

## Overview

ZenTune (formerly UXTU4Linux) is a power management tool for **AMD Ryzen APUs and desktop CPUs** on Linux and macOS. Talks to the CPU through PCI direct access on most systems, or through [ryzen_smu](https://github.com/amkillam/ryzen_smu) when Secure Boot is on. Set power limits, temperature limits, VRM currents, clocks and Curve Optimiser without touching the BIOS. The terminal UI runs as your normal user; a root daemon handles the hardware writes.

- Built-in Eco / Balance / Performance / Extreme presets for Ryzen APUs, desktop CPUs and Framework Laptops
- Adaptive Mode (Linux only): tunes power limit, Curve Optimiser and iGPU clocks live from temperature and load; savable presets and auto-start
- Custom Preset Editor with ~65 parameters on APUs: power/temp limits, VRM currents, clock targets, per-core CO, static OC
- System settings inside presets: power profile, ASUS performance mode / GPU Eco / MUX, CCD affinity on dual-CCD chips
- NVIDIA dGPU clock limits and core/mem offsets
- Home tab with live CPU temp, power, clock and load graphs
- Automations: switch presets on AC/battery and on resume
- Reapply loop so other tools can't silently undo your settings
- Status tab shows which SMU commands were accepted or rejected
- Built-in updater that preserves your config and custom presets

---

## Compatibility

| Platform | Status |
|----------|--------|
| Linux with systemd, Python 3.10+ | Actively supported |
| Linux without systemd (OpenRC, runit, etc.) | Supported: installer sets everything up, you start the daemon manually |
| macOS (Hackintosh, AMD CPU) | Supported: tuning, presets and automations work; Adaptive Mode is Linux-only for now |
| Intel | Not supported |

> [!NOTE]
> **ryzen_smu is only required on Linux when Secure Boot is enabled.** PCI direct access works on most Linux systems without any kernel module, and on macOS the daemon talks to the SMU through [DirectHW](https://github.com/joevt/directhw) or the kext-free IOPCIBridge path instead. If Secure Boot is on, install ryzen_smu ≥ 0.1.7 and enroll the signing key; the [Wiki](../../wiki) has per-distro steps.

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

## Star History

<a href="https://www.star-history.com/?repos=HorizonUnix%2FZenTune&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=HorizonUnix/ZenTune&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=HorizonUnix/ZenTune&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=HorizonUnix/ZenTune&type=date&legend=top-left" />
 </picture>
</a>

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