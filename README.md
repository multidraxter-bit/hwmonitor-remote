# HWMonitor Remote

Standalone desktop app for Fedora that monitors a Windows machine's hardware sensors over SSH or HTTP.

## Product direction

This project is being shipped as a standalone RPM desktop app.
The old Plasma widget files remain in the repo as legacy reference material, but they are not the release target.

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

## RPM package

Fedora RPM packaging files are in:

- `packaging/rpm/hwmonitor-remote.spec`
- `packaging/linux/hwremote-monitor.desktop`
- `packaging/linux/icons/hicolor/*/apps/hwremote-monitor.png`

Built package path on this machine:

```text
/home/loofi/rpmbuild/RPMS/noarch/hwmonitor-remote-0.3.0-1.fc43.noarch.rpm
```

The standalone app now ships with a custom `hwremote-monitor` launcher icon generated from `logo.png`.
Runtime icon assets for the app window live in `assets/icons/`.

## Optional mode: HTTP exporter

If you later want the Windows machine to expose a local HTTP endpoint instead of per-refresh SSH calls:

- `windows/lhm-exporter.ps1`: headless HTTP exporter using `LibreHardwareMonitorLib.dll`
- `windows/install-exporter.ps1`: helper to install/start it

Expected endpoints:

- `http://WINDOWS_IP:8086/health`
- `http://WINDOWS_IP:8086/data.json`

## Legacy Plasma widget files

The repo still contains the old Plasma widget package in `plasmoid/package`, but ongoing work is focused on the standalone RPM app.
