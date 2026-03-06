# HWMonitor Remote

Standalone desktop app for Fedora that monitors a Windows machine's hardware sensors over SSH or HTTP.

## Default mode: SSH snapshots

This is the default and most reliable path for your setup.

- `windows/lhm-snapshot.ps1`: grabs a full sensor snapshot once over SSH
- `fedora/hwmonitor_remote.py`: standalone desktop app

Default target:

```text
ssh://loofi@192.168.1.3
```

Launch the app:

```bash
hwremote-monitor
```

The launcher points to:

```bash
/home/loofi/hwremote-monitor/fedora/hwmonitor_remote.py
```

## Optional mode: HTTP exporter

If you later want the Windows machine to expose a local HTTP endpoint instead of per-refresh SSH calls:

- `windows/lhm-exporter.ps1`: headless HTTP exporter using `LibreHardwareMonitorLib.dll`
- `windows/install-exporter.ps1`: helper to install/start it

Expected endpoints:

- `http://WINDOWS_IP:8086/health`
- `http://WINDOWS_IP:8086/data.json`

## Plasma widget

The repo still contains the optional Plasma widget package in `plasmoid/package`, but the desktop app is the primary target now.
