# AGENTS.md — HWMonitor Remote

## Project

- Active product target: the standalone Fedora RPM desktop app.
- Supporting surfaces:
  - `windows/` — Windows snapshot/exporter collectors
  - `fedora/` — active Tkinter desktop app and transport helpers
  - `plasmoid/` — legacy Plasma widget kept as reference material
  - `packaging/` — RPM packaging assets
- Unless the user explicitly asks for the plasmoid, optimize for the Fedora desktop app first.

## Commands

- `python fedora/hwmonitor_remote.py` — run the desktop app directly
- `python -m pytest tests/ -v` — run the current pytest suite
- `./scripts/build-rpm.sh` — build the RPM
- `./scripts/install-rpm.sh` — install the RPM
- `./scripts/uninstall-rpm.sh` — uninstall the RPM
- `python fedora/fetch_snapshot.py --source ssh://loofi@192.168.1.3` — manual SSH snapshot fetch helper

## Architecture

`Windows collectors -> merged telemetry JSON -> Fedora Tkinter app (active) / Plasma plasmoid (legacy)`

- `windows/lhm-snapshot.ps1` and `windows/lhm-exporter.ps1` are the upstream data producers.
- `windows/telemetry-common.ps1` owns the merged JSON tree contract shared by multiple consumers.
- `fedora/hwmonitor_remote.py` is the main desktop app and currently contains UI, transport, alerting, and persistence logic.
- `plasmoid/package/` consumes the same payload schema, but is not the current release target.

## Conventions

- Treat telemetry JSON shape as a shared contract; changing it has cross-surface blast radius.
- Preserve the Windows PowerShell 5 re-exec behavior unless the task explicitly replaces that compatibility strategy.
- Treat hardcoded machine-specific paths and hosts as configuration debt to improve carefully, not as generic defaults to spread further.
- When changing versioned packaging, keep `scripts/build-rpm.sh`, `packaging/rpm/hwmonitor-remote.spec`, and user-facing docs aligned.
- Do not change both the Fedora app and legacy plasmoid unless the request clearly requires both.

## Key Files

- `fedora/hwmonitor_remote.py` — active desktop UI and logic
- `fedora/fetch_snapshot.py` — transport helper / manual fetch path
- `windows/telemetry-common.ps1` — shared telemetry schema builder
- `windows/lhm-snapshot.ps1` — one-shot collector
- `windows/lhm-exporter.ps1` — HTTP exporter
- `plasmoid/package/contents/ui/main.qml` — legacy widget UI
- `packaging/rpm/hwmonitor-remote.spec` — RPM packaging metadata

See `README.md` and `docs/user-guide.md` for operator-facing setup and packaging context.
