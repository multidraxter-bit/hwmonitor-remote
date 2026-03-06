# HWMonitor Remote

Standalone desktop app for Fedora that monitors a Windows machine's hardware sensors over SSH or HTTP.

## Quick links

- User guide: `docs/user-guide.md`
- Packaging notes: `packaging/README.md`
- Linux desktop app: `fedora/hwmonitor_remote.py`
- Windows collectors: `windows/`

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
/home/loofi/Projects/hwremote-monitor/fedora/hwmonitor_remote.py
```

## RPM package

Fedora RPM packaging files are in:

- `packaging/rpm/hwmonitor-remote.spec`
- `packaging/linux/hwremote-monitor.desktop`
- `packaging/linux/icons/hicolor/*/apps/hwremote-monitor.png`

Built package path on this machine:

```text
/home/loofi/rpmbuild/RPMS/noarch/hwmonitor-remote-0.3.1-1.fc43.noarch.rpm
```

The standalone app now ships with a custom `hwremote-monitor` launcher icon generated from `logo.png`.
Runtime icon assets for the app window live in `assets/icons/`.

Recent desktop features:

- saved source presets for fast switching between hosts/endpoints
- source-aware browsing with `All`, `Alerts`, `HWiNFO`, and `Native` quick scopes
- compact mode for hiding noisy HWiNFO counters without losing them from search
- active alerts panel for one-click focus on problem sensors
- top movers panel for spotting the fastest-changing metrics
- richer sensor detail with session average, spread, thresholds, and trend context
- per-sensor alert muting plus custom warning/critical threshold overrides
- dashboard telemetry strip showing source health, snapshot age, focus, and alert totals

## User guide

The end-user walkthrough with screenshots lives here:

```text
docs/user-guide.md
```

## Optional mode: HTTP exporter

If you later want the Windows machine to expose a local HTTP endpoint instead of per-refresh SSH calls:

- `windows/lhm-exporter.ps1`: headless HTTP exporter using `LibreHardwareMonitorLib.dll`
- `windows/install-exporter.ps1`: helper to install/start it

Expected endpoints:

- `http://WINDOWS_IP:8086/health`
- `http://WINDOWS_IP:8086/data.json`

## Optional telemetry integrations

The Windows collector can merge extra telemetry from:

- HWiNFO shared memory or log CSV fallback
- PresentMon CSV
- MSI Afterburner log CSV

How it works:

- `windows/lhm-snapshot.ps1` and `windows/lhm-exporter.ps1` now both load `windows/telemetry-common.ps1`
- if `windows/telemetry-sources.json` exists, the collector reads the configured external files and adds them as extra hardware nodes in the same JSON tree
- the Fedora app does not need a separate transport for these sources; they arrive in the normal snapshot payload

Setup:

1. Copy `windows/telemetry-sources.example.json` to `windows/telemetry-sources.json`
2. For HWiNFO, prefer `"mode": "shared_memory"` and make sure `Shared Memory Support` is enabled in HWiNFO
3. Point any CSV-based sources to the log/CSV file you want to ingest
4. Set `"enabled": true` for the sources you want
5. Run the normal snapshot script or exporter

Notes:

- HWiNFO shared-memory mode is preferred; CSV remains as fallback
- MSI Afterburner integration is currently log-file based
- PresentMon integration reads the latest row from a CSV output file
- columns can be filtered or renamed in `telemetry-sources.json`
- all optional integrations fail soft: missing files simply produce no extra source node

## Legacy Plasma widget files

The repo still contains the old Plasma widget package in `plasmoid/package`, but ongoing work is focused on the standalone RPM app.
