---
description: "Use when editing Windows telemetry collectors or helpers in HWMonitor Remote. Covers the shared JSON contract, PowerShell 5 compatibility, fail-soft optional telemetry sources, and path-handling gotchas."
applyTo: "windows/**"
---

# Windows Telemetry Guidelines

- Treat the merged JSON payload as a compatibility contract shared with the Fedora desktop app and the legacy plasmoid.
- Preserve the current Windows PowerShell 5 compatibility behavior unless the task explicitly replaces it end-to-end.
- Keep optional telemetry integrations fail-soft: missing files or unavailable sources should not crash the collector pipeline.
- Be conservative with path handling and quoting, especially when composing commands or reading external telemetry sources.
- Never expose secrets, cookies, or machine-specific credentials in logs, docs, or generated examples.
