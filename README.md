# HWMonitor Remote

Lightweight remote monitor with an `HWMonitor`-style tree layout on Fedora.

## Default mode: SSH snapshots

This is the default and most reliable path for your setup.

- `windows/lhm-snapshot.ps1`: grabs a full sensor snapshot once over SSH
- `fedora/hwmonitor_remote.py`: polls that snapshot and renders it locally

Default target:

```text
ssh://loofi@192.168.1.3
```

Launch:

```bash
hwremote-monitor
```

## Optional mode: HTTP exporter

If you later want the Windows machine to expose a local HTTP endpoint instead of per-refresh SSH calls:

- `windows/lhm-exporter.ps1`: headless HTTP exporter using `LibreHardwareMonitorLib.dll`
- `windows/install-exporter.ps1`: helper to install/start it

Expected endpoints:

- `http://WINDOWS_IP:8086/health`
- `http://WINDOWS_IP:8086/data.json`

## Plasma widget

Native Plasma applet package:

- `plasmoid/package`

Installed applet id:

```text
com.github.loofi.hwremotemonitor
```

Install manually:

```bash
kpackagetool6 --type Plasma/Applet --install /home/loofi/hwremote-monitor/plasmoid/package
```
