# Design: Alert System + UI Cleanup

**Date:** 2026-03-06
**Repo:** hwmonitor-remote
**File:** `fedora/hwmonitor_remote.py`

## Problem

Two weaknesses in the current app:

- **Clutter:** The right (explorer) pane duplicates data already visible in the left (overview) pane, and the detail panel occupies space even when nothing is selected.
- **No alerts:** There is no way to be notified when a sensor breaches a dangerous threshold — the user must actively watch the window.

## Goals

1. Remove redundant UI panels to give the sensor tree more room.
2. Add an in-app alert banner that surfaces critical/warn sensors at a glance.
3. Add system tray integration with desktop notifications on alert state changes.

---

## Section 1: Layout Cleanup

### What to remove

| Element | Location | Reason to cut |
|---|---|---|
| `dashboard_bar` | Explorer pane, above sensor tree | Duplicates the summary cards (CPU/GPU/Drive) on the left panel |
| `favorites_bar` | Explorer pane, above sensor tree | Duplicates `favorites_tree` on the left panel |

### Detail pane collapse

Currently the "Selected Sensor" detail block at the bottom of the explorer pane is always visible with placeholder text. After cleanup:

- Hidden by default (zero height, not packed).
- Shown automatically when `tree.selection()` becomes non-empty.
- Hidden again when selection is cleared.

This recovers ~100px of vertical space for the sensor tree when the user is browsing without a selection.

---

## Section 2: Alert System

### 2a — In-app alert banner

A horizontal strip packed just below the header bar, hidden by default.

- **Shown** when one or more sensors are at `warn` or `critical` severity.
- **Content:** compact list of offending sensors, e.g. `CPU Package 94 C  |  GPU Load 97%`
- **Color:** amber background for warn-only, red background when any critical.
- **Dismiss button (x):** hides the banner for the current refresh cycle; reappears on next refresh if sensors are still over threshold.
- **Auto-hides** when all sensors return to normal.

### 2b — System tray (pystray + Pillow)

New optional dependency: `pystray`, `Pillow`.

- App gets a system tray icon on launch.
- Minimizing the window hides it to the tray instead of the taskbar.
- Tray right-click menu: **Open**, **Refresh**, **Quit**.
- If `pystray` is not installed, tray support is silently skipped (app works as before).

### 2c — Alert state tracking and notification logic

```
self.alert_states: dict[str, str]   # sensor_path -> last known severity
```

On each refresh, after `_apply_data`:

1. Compute severity for all sensors via existing `_severity()`.
2. For each sensor at `warn` or `critical`:
   - If severity is *worse* than `alert_states[path]` (or path is new), fire a tray notification and update state.
   - "Worse" order: `normal < warn < critical`.
3. For sensors that recovered to `normal`, remove from `alert_states` silently.
4. Update the in-app banner with the current list of offending sensors.

Notification body: `"CPU Package: 94 C (critical)"` — one notification per newly-worsened sensor per refresh cycle. No repeat spam on stable alerts.

---

## Dependencies

| Package | Purpose | Optional |
|---|---|---|
| `pystray` | System tray icon + menu | Yes — graceful fallback |
| `Pillow` | Required by pystray for icon rendering | Yes — same fallback |

Both are available via `pip` and can be added to the RPM spec as weak dependencies.

---

## Files Changed

- `fedora/hwmonitor_remote.py` — main implementation
- `packaging/rpm/hwmonitor-remote.spec` — add weak deps for pystray/Pillow
- `README.md` — document optional tray deps

---

## Out of Scope

- Configurable per-sensor thresholds (use existing hardcoded values: 90 C critical, 75 C warn, 95% load critical)
- History persistence to disk
- Multiple host support
