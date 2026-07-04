---
name: Bug report
about: Report a problem with ZenTune
title: "[Bug]: "
labels: bug
assignees: ''

---

<!-- Before opening an issue, please check the Troubleshooting wiki page
and search existing issues first. -->

## What happened?

<!-- A clear description of the bug and what you were doing when it occurred. -->

## Expected behavior

<!-- What did you expect to happen instead? -->

## Steps to reproduce

1.
2.
3.

## Affected component

<!-- Delete the ones that don't apply -->
- SMU backend (applying settings / SMN access)
- Daemon / systemd service
- TUI / CLI
- Custom Preset Editor
- Automations / Override (AC/battery/resume)
- Installation / setup

## Environment

- ZenTune version: <!-- e.g. v2.0.0 or commit hash -->
- CPU model: <!-- e.g. AMD Ryzen 7 7735HS -->

## System information

<!-- Run these and paste the output -->

```
uname -a
cat /etc/os-release 2>/dev/null || sw_vers   # sw_vers on macOS
python3 --version
cat /sys/kernel/ryzen_smu_drv/drv_version 2>/dev/null || echo "ryzen_smu not loaded"   # Linux only
grep -E "^cpu family|^model|^model name" /proc/cpuinfo 2>/dev/null \
    || sysctl machdep.cpu.family machdep.cpu.model machdep.cpu.brand_string   # macOS
```

## Daemon logs

<!-- Linux: journalctl -u zentune.service -n 50 --no-pager
     macOS: tail -100 /var/log/zentune.log -->

```

```

## App config

<!-- cat /opt/zentune/src/Assets/config.ini (remove anything sensitive) -->

```ini

```

## Additional context

<!-- Screenshots, dmesg output, whether it worked in a previous version, etc. -->
