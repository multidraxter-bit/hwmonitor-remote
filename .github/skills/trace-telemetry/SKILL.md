---
name: trace-telemetry
description: 'Trace telemetry fields from Windows collectors through the shared JSON contract into the Fedora app and legacy plasmoid in HWMonitor Remote. Use when changing payload shape, adding sensor fields, or debugging missing telemetry.'
argument-hint: 'Describe the field, sensor, or payload section to trace'
---

# Trace Telemetry

## When to Use

- A sensor field appears on Windows but not in Fedora
- A telemetry change may affect multiple consumers
- You need to understand the blast radius of JSON contract changes
- You are debugging source-specific regressions across `windows/`, `fedora/`, and `plasmoid/`

## Procedure

1. Find the field producer in `windows/lhm-snapshot.ps1`, `windows/lhm-exporter.ps1`, or `windows/telemetry-common.ps1`.
2. Trace how the field is normalized and merged into the shared JSON payload.
3. Locate Fedora-side usage in `fedora/hwmonitor_remote.py` or transport helpers.
4. Check whether the legacy plasmoid also consumes the same field or payload section.
5. Prefer compatibility-preserving changes and call out every affected surface before editing.

## Guardrails

- Treat the Windows payload as a shared contract, not a single-app internal detail.
- Preserve Windows PowerShell 5 compatibility behavior unless the task explicitly replaces it.
- Avoid copying hardcoded host or path assumptions into new code without surfacing them as configuration debt.
