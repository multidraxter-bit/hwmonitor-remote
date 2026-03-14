---
name: "Trace telemetry flow"
description: "Trace a telemetry field or sensor from the Windows collector through the Fedora app and legacy plasmoid."
argument-hint: "Describe the field, sensor, or payload section to trace"
agent: "agent"
---
Trace the requested telemetry field through HWMonitor Remote.

Include:
1. Where the data is produced in `windows/`
2. How it is normalized or merged
3. Where the Fedora app consumes it
4. Whether the legacy plasmoid depends on it too
5. What needs to stay compatible if the field changes
