---
description: "Use when editing the legacy plasmoid in HWMonitor Remote. Covers the reference-only status of plasmoid/, shared telemetry-schema compatibility, and when to avoid widget-first changes."
applyTo: "plasmoid/**"
---

# Legacy Plasmoid Guidelines

- `plasmoid/` is reference material unless the task explicitly targets the KDE widget.
- Prefer fixing shared data or helper logic in ways that keep the active Fedora desktop app correct first.
- Preserve compatibility with the shared telemetry JSON contract consumed from the Windows side.
- Call out any hardcoded helper paths or host-specific assumptions instead of silently copying them into new code.
- If a task only mentions the RPM app or Fedora UI, do not expand scope into the plasmoid.
