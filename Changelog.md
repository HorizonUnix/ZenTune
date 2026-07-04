## [2.0.0]

UXTU4Linux is now **ZenTune**. This release drops the `dmidecode` system dependency, adds a way to override detected CPU info, adds macOS support

### Hardware detection
- **No more dmidecode.** CPU identity and board info are now read from `/proc/cpuinfo`, `/sys`, and `zenmaster`, which every distro already exposes.
- **Hardware tab shows Device and Processor only.** Memory Information (RAM manufacturer/part number/speed, which only ever came from dmidecode's SMBIOS read), Battery Information (health/cycle detail), and Processor's cores/threads/clock/cache rows have all been dropped. The Processor card now shows exactly what's detected (name, codename, architecture, signature).
- **Edit CPU info.** A new "Edit CPU info" button in Settings lets you override the detected CPU name, useful for demoing a different model's premade preset. It doesn't change your real detected architecture/family, so it can't affect how the daemon talks to your actual hardware.

### macOS support
- **ZenTune now runs on macOS** (Hackintosh, AMD Ryzen CPU). Tuning, presets and automations all work the same as on Linux.
- **Two SMU access paths.** The daemon reaches the CPU through the [DirectHW](https://github.com/joevt/directhw) kernel extension, or a kext-free fallback through IOKit's `IOPCIBridge` service (needs the `debug=0x144` boot-arg, tuning only, no live sensor graphs). See the [macOS Installation guide](https://github.com/HorizonUnix/ZenTune/wiki/macOS-Installation).
- **launchd instead of systemd.** The background daemon installs as a `launchd` job (`com.horizonunix.zentune`) and gets the same in-app management (install/restart/view logs/uninstall) as the systemd service on Linux.
- **Startup backend check.** If neither DirectHW nor the kext-free fallback is usable, the app now shows a clear message pointing at the install guide, instead of silently failing to apply presets, matching the existing Secure Boot/ryzen_smu check on Linux.
- **Adaptive Mode stays Linux-only for now.** The tab and its Settings toggle are hidden automatically on macOS.

### Updates and repair
- **Dependencies always stay current.** Both the in-app updater and the daemon's "Install / repair" action now always upgrade to the latest versions pinned in `requirements.txt`, instead of only installing what's missing. This closes a gap where the daemon's venv bootstrap didn't even check for `zenmaster`.
- **Manual runs fail cleanly.** Running `UXTU4Linux.py` directly without `pip install -r requirements.txt` first now shows a clear message telling you what to install, instead of a raw traceback.

### Renamed to ZenTune
- **UXTU4Linux is now ZenTune.** Install paths, the systemd service, the socket, and the `zentune` command have all moved to match. Config and custom presets carry over automatically.
- **v1.1.0 users migrate automatically.** If you're still on v1.1.0, using "Check for updates" one more time will walk you through a one-time automatic migration to ZenTune.

**Full changelog:** https://github.com/HorizonUnix/ZenTune/compare/1.1.0...2.0.0

## [1.1.0]

The headline addition is PCI direct access: the daemon now talks to the CPU without ryzen_smu on most systems. ryzen_smu is only needed when Secure Boot is on, because kernel lockdown blocks raw PCI config writes in that case. The Status tab was reworked to show adaptive state alongside daemon state in one panel, the Home tab picked up iGPU graphs, and the installer now handles non-systemd setups and distros with no supported package manager.

### New PCI direct access backend
- **No kernel module on most systems.** When Secure Boot is off, the daemon accesses the SMU through the northbridge PCI config space directly. ryzen_smu is still required when Secure Boot is on.

### Status tab
- **Merged into one panel.** Adaptive state, automations and SMU output are now all in the main status panel instead of a separate card. The panel refreshes every second while the tab is open.

### Home tab
- **iGPU graphs.** iGPU clock and usage graphs are now shown on APUs when the hardware supports it.

### Version mismatch detection
- **Notify on version mismatch.** If the running daemon is a different version than the TUI, the app shows a warning at startup. Usually happens after a partial update; restart the daemon to fix it.

### Updater
- **Deps reinstalled on update.** The updater now reinstalls `requirements.txt` into the venv as part of the update, so a new dependency added in a release is picked up automatically. (Fixed #98)

### Under the hood
- **Code cleanup and performance.** Dead code removed across the daemon, TUI and engine. The status refresh loop was simplified and the async thread count reduced. Several hot paths were tightened to lower CPU overhead during idle polling.
- **Bug fixes.** Various minor bugs fixed across the TUI, daemon and update flow.

**Full changelog:** https://github.com/HorizonUnix/UXTU4Linux/compare/1.0.0...1.1.0

## [1.0.0]

After two years of development, UXTU4Linux finally reaches 1.0.0 with all the core features in place. The headline addition is Adaptive Mode: instead of holding one fixed preset, the app now tunes your CPU live from temperature and load. The Home tab gained live graphs, Automations were rebuilt to be simpler, and the whole codebase was reorganized underneath.

> **Updating from v0.9.x and v0.8.x?** v1.0.0 adds one new dependency (`textual-plotext`, used for the Home graphs). Re-run the installer above to pick it up while keeping your settings and custom presets.

Prefer not to reinstall? Add it to the existing environment by hand, then restart the daemon:

```bash
/opt/uxtu4linux/venv/bin/pip install textual textual-plotext
sudo systemctl restart uxtu4linux.service
```

### Adaptive Mode
- **Live tuning.** A new Adaptive Mode tab raises and lowers your power limit from temperature and load, keeping the chip as fast as it can run within the temperature you set.
- **More than power.** It can also tune the all-core Curve Optimiser, push and pull the iGPU clocks, hold an ASUS power profile and tune an NVIDIA dGPU, all on the same loop.
- **Your own adaptive presets.** Save, duplicate and delete adaptive presets just like custom ones, and have the daemon start your chosen one automatically on boot.

### Live Home dashboard
- **Real-time graphs.** The Home tab now plots CPU temperature, power, clock and usage as they happen, alongside the quick links to every other tab.

### Automations
- **Override switch removed.** Automations are active whenever you set a Battery Charge or Battery Discharge preset. Leave a slot empty to keep whatever is already applied for that power state.
- **Apply any time.** Applying a preset by hand is no longer blocked while automations are set; the automation simply re-applies the right preset on the next AC/battery change.

### Settings
- **Choose your starting tab.** Pick which tab the app opens on from Settings.

### Under the hood
- A large reorganization of the daemon and the interface into smaller, focused modules, plus dead-code cleanup, for a cleaner and more maintainable foundation.

### Note
- With official UXTU support for Linux on the way, this release marks the completion of the project: from now on there will only be bug fixes and improvements. If you want to add new features and have some development experience, take a look at https://github.com/HorizonUnix/UXTU4Linux/wiki/Developer-Documentation to learn more about UXTU4Linux and become a contributor!

**Full changelog:** https://github.com/HorizonUnix/UXTU4Linux/compare/0.9.1...1.0.0

## [0.9.1]

### NVIDIA Tuning

* NVIDIA tuning has been fully migrated to NVML and no longer relies on the `nvidia-smi` command. GPU power limit and clock lock controls now call the NVIDIA driver directly through NVML alongside the core and memory offsets that already use it.

* **Desktop NVIDIA GPU power limit support.** You can now set a power limit on desktop NVIDIA GPUs. The control reads your GPU's actual power limit range and current value from NVML, then adjusts the minimum, maximum, and current values to match your hardware. On laptop GPUs, where power limits are controlled by Dynamic Boost and cannot be adjusted (NVML reports `NOT_SUPPORTED`), the control is automatically hidden.

* **Wider GPU clock offset ranges.** Core and memory clock offsets now support values from -1000 MHz to +4000 MHz.

### New NVIDIA ROP Check

* **NVIDIA ROP check for RTX 4000 and 5000 series GPUs.** On startup, UXTU4Linux now reads your GPU's actual ROP count and warns you if it is lower than the expected value for your model.

### Premade Presets

* **See the command.** Selecting a premade preset now displays the exact command being applied in a dedicated output box, so you can always see what is being sent to your CPU.

**Full changelog:** https://github.com/HorizonUnix/UXTU4Linux/compare/0.9.0...0.9.1

## [0.9.0]

Starting from v0.9.0, we reimagine how you interact with UXTU4Linux. The entire interface is new, built from the ground up on Textual: a fast, modern terminal app you drive with the mouse or the keyboard. Tuning your Ryzen CPU has never felt this effortless on Linux.

Everything now lives in one window, organized into tabs you can reach in an instant. Apply a preset, craft your own, set up automations, and watch your CPU's live status, all without leaving the screen.

> **Updating from v0.8.x?** v0.9.0 adds a new dependency (Textual), so the interface won't start until your virtual environment has it. The easiest path is to re-run the installer, which now installs the requirements for you and keeps your settings and custom presets:

```bash
curl -fsSL https://raw.githubusercontent.com/HorizonUnix/UXTU4Linux/main/install.sh | bash
```

Prefer not to reinstall? Add the dependencies to the existing environment by hand, then restart the daemon:

```bash
/opt/uxtu4linux/venv/bin/pip install textual pyzmq
sudo systemctl restart uxtu4linux.service
```

### A brand-new interface
- **Tabs, not menus.** Home, Premade Presets, Custom Presets, Automations, System Info, Status and Settings, each one a keystroke or a click away.
- **Mouse and keyboard.** Point and click, or fly through with number keys. Whatever feels natural.
- **Themes.** Choose a look that suits you. Your choice is remembered.
- **A guided first run.** A three-step setup wizard installs the background service and detects your hardware on its own, then gets out of your way.

### Presets, refined
- **Premade presets** apply in a single tap, each with a clear description of what it does.
- **The Custom Preset Editor, rebuilt** as a live form: flip a switch, type a value, apply or save. Sections appear only for what your chip actually supports.

### Automations that just work
- Switch presets automatically between AC and battery, and re-apply on resume from sleep, suspend or hibernation.
- Plain-language explanations throughout, so it's clear what every option does before you turn it on.

### Live status, at a glance
- A dedicated Status tab shows the active preset, your automations, the power source, and the exact result of the last apply. It refreshes as things change, and follows your reapply interval.

### Rock-solid by design
- The app and the background daemon now stay perfectly in step. Every change you make is reflected instantly and accurately.
- Updating never touches your settings. Re-running the installer keeps your configuration and your custom presets exactly as they were.

### Under the hood
- A ground-up reorganization of the codebase for a cleaner, faster and more maintainable foundation.

**Full changelog:** https://github.com/HorizonUnix/UXTU4Linux/compare/0.8.1...0.9.0

## [0.8.1]

A small follow-up to v0.8.0 with quality-of-life polish and fixes.

### Improved
- The `ApplyOnStart` setting now defaults to 0 (disabled).
- **Live Daemon Status screen**: it now refreshes on its own while auto-reapply is running, so the power source, active preset and last-apply result stay up to date.
- **Clearer NVIDIA feedback**: capping the GPU clock and setting core/VRAM offsets now report failures (including the driver's error).
- **More reliable cache-size detection** in Hardware Information.

### Internal
- Removed unused code across the SMU, IPC and daemon modules.

## [0.8.0]

Starting from v0.8.0 we rebuilt UXTU4Linux from the ground up. The old version relied on a bundled `ryzenadj` binary to do the actual work; this one talks to your CPU directly, the same way the original Universal x86 Tuning Utility does on Windows. Along the way almost every part of the app got reworked: the preset engine, the Custom Preset Editor, the background daemon, the installer, the logs and the documentation. It is the biggest release UXTU4Linux has ever had, and the closest it has ever been to the real UXTU experience on Linux.

## Talks to your CPU directly

UXTU4Linux now sends commands straight to the CPU through the [ryzen_smu](https://github.com/amkillam/ryzen_smu) kernel module, and every command was checked one-to-one against the original UXTU, so presets behave exactly like they do on Windows. You also get honest feedback: the app shows you which commands your CPU accepted and which it rejected, instead of just hoping for the best.

> **Heads up before you update**: this release needs the `ryzen_smu` kernel module (version 0.1.7 or newer). It takes a few minutes to set up and the [installation guide](https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Installation#2-install-the-ryzen_smu-kernel-module) walks you through it step by step for your distro, Secure Boot included.

## Your presets can now control the whole machine

The Custom Preset Editor has a new System section, so one preset can set up everything at once:

- **Power Profile**: Power Saver, Balanced or Performance.
- **ASUS Performance Mode**: Silent, Balanced or Turbo fan modes on ASUS laptops.
- **ASUS GPU Eco**: turn the discrete GPU off to save battery.
- **ASUS GPU MUX**: switch between dGPU (Ultimate) and Optimus (Hybrid) mode. Applies after a reboot.
- **CCD Affinity**: on dual-CCD CPUs like the X3D chips, keep your games on the V-Cache die.

And if you have an NVIDIA card, the editor can now cap its max clock and set core/VRAM offsets too.

## More to tune

New fields in the editor: AMD Boost Profile, PBO Scalar, soft clock limits (CPU, Infinity Fabric, SoC, video engine and data clocks), and static overclocking with CPU clock and voltage. Every field has the same description as the original UXTU, so guides written for the Windows version apply directly.

## Easier to live with

- **Logs you can actually read**: the daemon now tells you what happened and why, like `Applied preset 'Eco' (power source changed from AC to battery).` or `Applied preset 'Performance' (woke from suspend after ~32m).`
- **Clearer errors**: if something is missing at startup, the app tells you exactly what and links you to the exact wiki section that fixes it, instead of dumping a wall of commands.
- **A proper status screen**: daemon version, power source, active preset, auto-reapply, automations and whether your last preset was accepted, all in one place.
- **A friendlier setup**: the first-run wizard is three clear steps, and there's a guided path for systems without systemd.
- **A smarter installer**: installs what it needs through your package manager and updates existing installations safely.

## Documentation

There's now a full [wiki](https://github.com/HorizonUnix/UXTU4Linux/wiki): step-by-step installation for every major distro, a troubleshooting page, a guide to the Custom Preset Editor, a reference explaining every single parameter, and developer documentation for contributors.

## Removed

- The bundled `ryzenadj` binary (replaced by the native backend)

## [0.7.1]

## What's new?
- Added support for the Curve Optimiser Per-Core (AMD CCD1/CCD2) in the Custom Preset Editor.

## [0.7.02]

## Hotfixes
- The daemon should never exit when detecting that Secure Boot is enabled and the kernel module is unsigned.

## Notes
- Support for Curve Optimizer Per-Core is postponed due to development branch conflicts and a lack of testing hardware.

## [0.7.01]

## What's new?
- Added support for the Curve Optimiser (All Core and iGPU) in the Custom Preset Editor.

### Note
- The Curve Optimiser may not work on your CPU, even if its generation is supported, as it is currently limited to Ryzen 9 SKUs.
- Support for Curve Optimiser Per-Core is planned for `v0.7.02` due to development branch conflicts and a lack of testing hardware.

## [0.7.0]

## What's new?

### Added

- **On Resume**: Configure a preset to apply automatically each time the system wakes from sleep or suspend
- `OnResume` config key for resume preset selection
- `Variant` config key to support Framework Laptop hardware detection and dedicated premade presets

### Improved

- Switched to the official musl static ryzenadj binary, replacing the manylinux build
- Consolidated 25 individual preset files from the `Presets/` folder into a single `presets.py` module for easier maintenance
- Added descriptions for AC and DC presets
- Renamed `custom_presets.json` to `custom.json`
- Various bug fixes
- Minor UI refinements
- General codebase cleanup

## [0.6.02]

## What's New

### Custom Preset Editor
Build your own power preset from scratch using a keyboard-driven editor. Tune temperature limits, power limits, VRM current limits, and iGPU clock speeds. All with real-time hints explaining what each setting does. Presets are saved by name and show up alongside the built-in presets everywhere in the app.

### Automations (Override)
Set a different preset for AC and battery automatically. When you plug in, the AC preset kicks in. When you unplug, the battery preset takes over. The daemon watches for power state changes in the background. Each slot is optional; leaving one as (None) just uses whatever preset you picked in Power Management for that state.

---

## Improvements

- **Preset descriptions**: hovering over Eco, Balance, Performance, or Extreme now shows a short description of what that preset does.
- **Hardware Information** now has a proper title and cleaner section layout.
- **Daemon logs** are cleaner and more readable in `journalctl`.
- **Version updates** now correctly rank `0.6.1` as newer than `0.6.01`.
- **Updates preserve your settings**: both `config.ini` and your custom presets are backed up and restored automatically during an update.

---

## Removed

- **Dynamic Mode** has been replaced by Automations. It was limited to Extreme on AC and Eco on battery with no flexibility.

## [0.6.01]

# What's New?
### New
- Hardware Information now includes a Battery section
  - Reads directly from kernel sysfs (/sys/class/power_supply/)
  - Shows status, charge level, health, cycle count, full charge, design capacity, and charge rate
  - Supports energy-based (µWh), charge × voltage, and raw mAh reporting depending on driver
  - Capacity reported in mWh where voltage data is available, mAh otherwise
  - Correctly identifies system battery over peripheral batteries (e.g. Logitech HID devices)

### Fixed
- TUI and Daemon now prevent duplicate instances
- Redundant startup log lines removed
- Debug setting changes in Settings now reload instantly in the running daemon without a restart

### Improved
- Daemon logging level now follows the Debug setting at startup (DEBUG vs INFO)
- Debug mode in the daemon now logs the ryzenadj command and per-loop tick state
- Secure Boot and ryzen_smu check moved to daemon startup
- Adjusted presets for AMDCPU
- Minor UI refinements

## [0.6.0]

## What's new?
Introduce a background daemon-based architecture for applying Ryzen power presets, modernize the terminal UI.

New Features:
- Add a systemd-managed background daemon with IPC for applying, looping, and dynamically switching RyzenAdj presets.
- Introduce a richer terminal menu UI with keyboard navigation, status-aware menus, and an About screen with update integration.
- Add system checks for Secure Boot blocking ryzen_smu and for dmidecode availability, guiding users with troubleshooting output.

Bug Fixes:
- Ensure preset and dynamic mode state is sourced from the daemon where possible, reducing drift between UI and applied settings.
- Harden handling of missing or invalid saved presets by falling back to the setup wizard or reporting clear errors.
- Validate RyzenAdj arguments in the daemon to avoid applying malformed or unsafe command payloads.

Enhancements:
- Refactor power management flow to use the daemon for all SMU operations, simplifying apply/reapply logic and centralizing dynamic mode handling.
- Improve hardware info parsing and presentation, including better dmidecode access via the daemon and clearer, styled output.
- Streamline settings into a single menu with toggleable options and an interval editor that immediately re-applies saved presets when changed.
- Update startup logic to verify and repair the systemd service path, auto-apply presets only when no mode is active, and enforce Linux-only support.
- Simplify and modernize config handling, version metadata, and menu structures across modules.

### Updating from `v0.5.x` may cause issues. Please refer to [Linux Installation Guide](https://github.com/HorizonUnix/UXTU4Unix/wiki/Linux-Installation)

## [0.5.22]

### macOS Deprecation Notice
- `v0.5.22` will be the last version to support the macOS branch.

## [0.5.21]

- Resolve issue #23 by implementing a robust search path for the `dmidecode` binary (`_find_dmidecode`) and storing its absolute path to prevent `PATH` resolution errors within `sudo` subshells (thx @kstutz01).
- Minor tweaks to `about.py` and `power.py`.
- Always `chmod +x` binaries when starting.
- Default sleep time is now `3`s instead of `30`s.

## [0.5.2]

# What's New?
- Cleaned up and refined most of the codebase after the huge refactor from `v0.5.0`

## [0.5.1]

# What's New?

## General
- Removed unused `SoftwareUpdate.py` standalone updater from the `Assets` folder
- Removed unused fields from `config.toml`: `Assets`, `voltage`, `max speed`,
  `current speed`, `core count`, `core enabled`, and `thread count`
- Implemented a new method for handling sudo and non-sudo command execution
- Implemented binary validation for `ryzenadj` and `dmidecode` at startup
- Implemented a new method to retrieve and display detailed hardware information

## Linux
- Added run-on-startup support via XDG Autostart with automatic config path registration
- Fixed an issue where `updater.py` could fail to relaunch the script after
  an update

## macOS
- Implemented a new method to re-register Login Items on startup

## [0.5.0]

# What's New?

### Architecture

The entire codebase has been rewritten from a single monolithic script into a proper Python package. `UXTU4Unix.py` is now a thin entry point; all logic lives in focused modules under `Assets/Modules/`.

```
UXTU4Unix/
├── UXTU4Unix.py
└── Assets/
    ├── SoftwareUpdate.py
    ├── Darwin/   ryzenadj, dmidecode
    ├── Linux/    ryzenadj
    ├── Presets/
    └── Modules/
        ├── config.py           central constants, paths, config singleton
        ├── hardware.py         CPU detection, codename, NVRAM check
        ├── power.py            preset loading, ryzenadj, dynamic mode
        ├── settings.py         all settings sub-menus
        ├── setup.py            first-run wizard, integrity check
        ├── ui.py               banner, clear, prompts
        ├── updater.py          version check, self-update
        ├── installer.py        macOS EFI/plist dependency installer
        ├── about.py            about screen
        └── secure_password.py  keyring wrapper
```

### New features

- **Dynamic Mode AC detection (Linux)** now correctly reads all AC adapter types (`Mains`, `USB`, `USB_C`, `USB_PD`, `USB_PD_DRP`, `USB_C_DRP`) and falls back gracefully on desktops with no battery - previously always returned `Extreme` on Linux.
- **Login Item path validation (macOS)** - stale Login Item entries (wrong path, moved app, leftover from Trash) are detected and removed automatically before re-registering the correct path.

### Bug fixes

- **Dynamic Mode preset args** - in reapply loop, Dynamic Mode now correctly fetches the actual preset arguments for `Extreme`/`Eco` from the preset table instead of passing the mode name string as ryzenadj args.

### Code quality

- Replaced long `if/elif` chains in codename detection with `match/case` (Python 3.10+).
- `_toggle_menu()` helper in `settings.py` eliminates six copy-pasted enable/disable sub-menus.
- Config access centralized, `config.py` owns all paths, constants, and the `ConfigParser` singleton; no module holds its own `cfg` object.
- `SoftwareUpdate.py` is now standalone (callable directly) and also used internally by `updater.py`, eliminating duplicated zip/swap logic.
  
## [0.4.2]

## What's New?
- Rework how dynamic mode works on Linux
- Update detection for new CPU models and presets from UXTU
- Resize the window to 80x35

## [0.4.1]

- Update `UXTU4Unix.command` for macOS

## [0.4.0]

### Starting from `v0.4.0`, UXTU4Unix has been completely rewritten.

## What's New?
- Merged `Linux` and `macOS` branches into a single main branch that supports both operating systems in the same file.
- Removed `logging`.

## Linux
- Added support for RyzenAdj version `0.17.0`.

## Note
- The `v0.4.x` series will be the last version to support macOS.
- Future development will focus on extending Linux support.
- Existed config file from `v0.3.x` will be reset due to incompatibility.
- Don't use Updater from `v0.3.x` because it may cause incompatibility issues between `v0.3.x` and `v0.4.x` so please access download the latest version from GitHub.

<img width="837" height="637" alt="Screenshot 2025-07-14 at 23 24 30" src="https://github.com/user-attachments/assets/3da9b765-2c4d-45cb-b4d8-10a20e321c12" />

## [0.3.3]

## General

- Updated CPU stepping code detection (based on https://github.com/JamesCJ60/Universal-x86-Tuning-Utility/blob/master/Universal%20x86%20Tuning%20Utility/Scripts/Family.cs)
- Updated CPU Presets (based on https://github.com/JamesCJ60/Universal-x86-Tuning-Utility/commit/3a4a5d5e9f16eb3d9f0db2c2ec1e77f37a1bb91a and https://github.com/JamesCJ60/Universal-x86-Tuning-Utility/commit/f58c6371954f6ff1945be4d3bcc84b4efd3641be)
- Updated RyzenAdj to latest commit https://github.com/FlyGoat/RyzenAdj/commit/8b0b7b915bf39a68d9f6be59c35a5ccd26b525cb

## Note
`UXTU4Unix` has entered the slow-development stage as `UXTU` is now planning to support the Linux platform. Since Hackintosh is also approaching end-of-life, this project will be deprecated once `UXTU` officially supports Linux.
## [0.3.2]

## General
- Support ryzenAdj v0.16.0
- Support macOS Sequoia

## [0.3.1]

## General

- Refactor code
- Fix DIR logic
- Fix `Custom` mode
- Fix some bugs

## macOS

- Extend Terminal window when called by `python3` command instead of `.command` file
## [0.3.03]

## General

- Fix `ReApply` settings logic
## [0.3.02]

- Moved from `AppleOSX` to @HorizonUnix
## [0.3.01]

## General
- Fix the detection order of `G` and `GE` APU.
- Remove the Intel check; RyzenAdj checks itself.
- Fix the issue with unsupported hardware
## [0.3.0]

## General
- Support CPU (Desktop CPU)
- Use UXTU codename instead of RyzenAdj for future support
- Improve logic to get presets
- Fix DIR
- Optimize code
- Get Family, Model to translate CPU/APU codename
- Use dmidecode to get CPU information
- Only get information for the first time, after that, read info from the config file
- Add a check for Intel chipset
- Fix logging file
### Linux
- Support Hardware Information
- Extend Terminal or Shell Window to 100x30
### macOS
- Use dmidecode from [Acidanthera](https://github.com/acidanthera/dmidecode)
## [0.2.9]

### General
- Fixed Phoenix support
- Removed Mendocino support because it is not supported by RyzenAdj
- Removed some old APU codenames and used RyzenAdj codenames instead
- Fixed some annoying issues with Settings, Apply preset, Dynamic mode, Auto reapply

## macOS
- Forced to use Py3 instead of Py2
- Removed SSL check due to some issues
- Fixed and synced DIR logic with Linux

## Linux
- Removed `SIP` settings because it is only for macOS
## [0.2.8]

### General
- Rename from `UXTU4Mac` to `UXTU4Unix`
- Support Linux (tested on Debian-based distro)
- Rework project structure
### macOS 
- Removed GPU/APU info
### Please download from GitHub if you failed update from built-in updater

## [0.2.7]

- Fixed a bug with the Updater
- Fixed a bug with CFU
- Reformatted CLI
- Improved support for Mendocino APU
## This is the first official commercial version for everyone, after numerous bug fixes and improvements
## [0.2.6]

- Extended APU support based on RyzenAdj
- Supported RyzenAdj v0.15.0
- Removed some information in Hardware information
- Added a logic to preset
## [0.2.5]

- Fixed a bug related to CFU
- Fixed various bugs related to the get_presets function
- Fixed the logic in the welcome_tutorial
- Added an SSL certificate check before running CFU to avoid hangs (thanks to @nlqanh524)
## [0.2.41]

- Fix various bug related to Welcome tutorial and get presets
- Fix filename

## [0.2.4]

- Extended presets based on UXTU's preset.
- Added support for each APU Generation Preset, similar to UXTU.
- Quick fix to Updater and CFU.
- Fix line error in `Hardware Information`
- New `9. Debug` under `Settings` to enable/disable some debug processes
### Currently, UXTU4Mac lacks CPU support because some commands in the original UXTU are incompatible with ryzenAdj.
## [0.2.32]

- Quick fix to Updater and CFU
### Please download from GitHub if you failed update from built-in updater
## [0.2.31]

- Fix line error in `Hardware Information`
- New `9. Debug` under `Settings` to enable/disable some debug processes
## [0.2.3]

## Software Update
- No longer keep Logs folder
## Apply Preset
- Fixed a stupid bug about sudo password
- Restored debug function

## [0.2.2]

### FIP:
- Removed/dropped support for FIP
- Removed FIP check in CFU
### Settings:
- Fixed various bugs related to `1. Preset` settings
- Fixed various bugs related to Dynamic Mode
- Reworked some logic
- Default config file is now located in `UXTU4Mac/Assets`
- New config file structure
### Welcome Tutorial:
- Improved some processes
### Hardware Information:
- Removed `Device Information`
- Removed `UXTU4Mac dependencies`
### Checks For Update:
- Now, if the script fails to fetch the latest version, it will retry 10 times. Afterward, it will ask whether to skip CFU or not.
### Other:
- Completely reworked the entire code structure
## [0.2.1]
## Input
- Improve user input handle
## .command file
- Default Terminal window when open now 100x30 instead of 80x20
## Other
- Reorder code structure
## [0.2.0]

### This update brings to you a similar experience from the UXTU from Windows
## Dynamic Mode
- Reworked dynamic mode logic
- Now, instead of tracking processes, it will track the battery to switch suit modes
- Added a new logical check: if it's still the same mode, it will not reapply
## Settings
- Added a new `4. Auto reapply` option under `Settings` to enable/disable auto reapply preset function
- Default setting will disable auto reapply
## Preset
- Properly ported preset from UXTU
- Added new presets `AC` and `DC` which are for some APU/CPU
## Other
- Using a new banner
- Displaying CPU name under the banner

## [0.1.9]

- Remove OcSnapShot
- Remove `DirectHW.kext` since ryzenAdj already do that with pciutils
- Fix a bug about Dynamic Mode
- New `SIP Flags` under Settings which change the required SIP flags
## [0.1.82]

- Proper support for Dynamic mode
- Fix various bug about Dynamic mode and preset
## [0.1.81]

- Fix a bug with Dynamic mode
## Please delete your old `config.ini` since it will not worked on this version
## [0.1.8]

- Support Dynamic mode aka Adaptive mode on UXTU, still in beta process
### Happy Women Day (8/3)!
## [0.1.73]

- Small changes to main menu, install menu and processes
## [0.1.72]

- Rework CLI
- Remove some function in About UXTU4Mac
- Improve logic
## [0.1.71]

- Small changes for code structure
## [0.1.7]

- Fix a serious bug about `apply_smu`
- Rework some code structure
- Rebrand with new logo for CLI
- New command file thanks to @corpnewt source code
- Better experience
- Optimize code
## [0.1.63]

- Fix a bug with built-in Updater
- Remove `sys` library
## [0.1.62]

- Fix a bug with CFU
- Fix a bug with `apply_smu`
- Change default SIP flags from `03080000` to `0B080000` which higher than `03080000`
### Please reinstall your kext and SIP through Settings -> Install UXTU4Mac Kexts
## [0.1.61]

- Rework `Settings` menu
- Proper support for Login Items
- Change SIP flags from `7F080000` to `03080000`
### Please reinstall your kext and SIP through Settings -> Install UXTU4Mac Kexts
## [0.1.6]

- Reworked the entire code structure
- Script now runs faster with better optimization
- Fix various bugs related to loops and other function
- Use While loop instead `threading` for `apply_smu` a.k.a `run_cmd`
## [0.1.52]

- Fix a bug with `Welcome` section
- Proper config file check before start script
## [0.1.51]

- Fix a bug when disable login items does not actually delete it
- Fix a bug with `run_cmd` and related
- Fix a bug with `Welcome` section
- Fix a bug with `About UXTU4Mac` section
- Now will check both FIP and CFU status before disable one of them due to some issues
## [0.1.5]

- Fix a lot of bug related to `Settings` and other sections
- Default sleep time now `10`s instead of `3`s
- New Time Sleep settings under `Settings` to set sleep time
- Improve handling about user option
  
## [0.1.4]

- Enhance FIP, more secure and safe
- Rework `Settings` and `Welcome` section
- Add a build number
- Add a new update name
- Now `Settings` have these section:
```
P. Preset setting
F. FIP setting
C. CFU setting
L. Login Items setting
S. Sudo Password setting
```

## [0.1.3]

- Support for Custom preset for config file
- Introduce FIP ( File Integrity Protection ) which protect main script file ( Beta ), disabled by default
- Now check SIP flags before running ryzenAdj

## [0.1.2]

- Fix a bug when Updater doesn't delete zip file after update
- Now script will restart itself after update
- Now script will check DirectHW.kext and debug=0x144 before running ryzenAdj
- New section name `UXTU4Mac dependencies` under About UXTU4Mac to check DirectHW.kext and debug=0x144

## [0.1.11]

- Add a tester list
- Make CLI look better with a little rework
- Fix a bug with Install kext and dependencies
- Fix a bug with About UXTU4Mac

## [0.1.1]

- Support backup `Logs` folder and `config.ini` when update UXTU4Mac
- Support show changelog on updater
- Fix a bug with CFU
- Now users have another option to specify config.plist path for install kext and dependencies
- Add a note after install kext and dependencies

## [0.1.0]

### Welcome to version series `0.1.x` with a better experience of using UXTU4Mac

- Include a B. Back button when applying the preset
- Add `I. Install kexts and dependencies (Beta)` to install kexts in `OC/Kexts/` and set SIP and `boot-args` automatically
- Now, when running the script, it will always apply the preset; users can press B to go back to the main menu
- Remove `SkipWelcome` in the config file
- Use OCSnapShot from @corpnewt for snapshot config files
- When running the script for the first time, it will install kexts automatically
- Improved welcome setup
- Cleaned up
- Fixed a bug with CFU
- Support Updater
- Add `LoginItems` to the config file
- Support force updating to the latest version under About UXTU4Mac
- Support applying presets from available presets beside loading from the config file
### Please delete your old `config.ini` since it's from the `0.0.x` series and incompatible with series `0.1.x`


## [0.0.98]

- Optimize code
- Add a logic to check sudo password
- Add a welcome tutorial (beta)


## [0.0.97]

- Supported for CPU codename and SMU version properly ( replace for the long dict in `0.0.96` )
- Add some warning and note
- Fix and add some hardware information
- Make output look cleaner


## [0.0.96]

- Support for more hardware information
- Fix a issue when no internet connection result a config override
### This will be the last update for `0.0.x` series


## [0.0.95]

- Support Hardware Information reader
- Switched to logging method
- Support logging to file ( Stored in `Logs` folder )
### This will be the last update for `0.0.x` series
![Screenshot 2024-02-12 at 22 30 00](https://github.com/gorouflex/UXTU4Mac/assets/98001973/c7faee7b-3f5c-49d7-9362-776206858795)
### 13/2/2024: Fixed a small issue when no internet connection result a config override

## [0.0.94]

- Bring back some UXTU preset
- Add a `SkipCFU` in config file to skip CFU when start (user customized)
- Adjust some guide


## [0.0.93]

- Support for Login Items in macOS ( aka Startup App )
- Refactored code


## [0.0.92]

- Supported for custom preset
- Fix image not being shown on CFU
- Rework structure


## [0.0.91]

- Optimize code
- Fix an issue when tool cannot instanly update config file


## [0.0.9]

### Change log

- Moved to @AppleOSX


## [0.0.8]

### Change log

- Removed useless Preset
- Add new `Auto` preset


## [0.0.7]

### Change log

- Fix args for `Performance` preset
- Add 3 `force` option for `Eco`, `Balance`, and `Extreme`

![image](https://github.com/gorouflex/RielUXTU4Mac/assets/98001973/05609b0d-94f7-4db8-9a2f-42739a38020c)


## [0.0.6]

### v0.0.6 introduces a new way for you to use `RielUXTU4Mac`
### This might the last version of `0.0.x` series
### With the support of @NotchApple1703 i will support GUI soon
### Change log
- New CLI
- New About menu
- New `skipwelcome` in config to skip welcome menu
- Adjust args for `Balance` and `Extreme` Preset

## [0.0.5]

### Change log
- Simplified and optimized code
- Now save password for the next run without require sudo password again
- Show current preset every loop


## [0.0.4]

### Change log
- Support CFU
- Support R&W config file
- Dropped supported for custom arg ( tempo )


## [0.0.3]

- Turn verbose on for debugging
- Add a clear screen function
- Fix GitHub file type

## [0.0.2]

### Change log
- Fix env ( 1 and 255 status code )


## [0.0.1]

### Change log
- Intial commit
- Support RyzenAdj v0.14.0

