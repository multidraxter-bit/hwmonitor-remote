# Dashboard Redesign & Sensor Grouping — Design

**Date:** 2026-03-07
**Status:** Approved

---

## Goal

Improve the Tkinter desktop app's visual design and usability by making summary cards severity-aware with progress bars, adding threshold reference lines to the detail sparkline, cleaning up the filter toolbar's active-state styling, and adding a hardware-level grouping toggle.

## Architecture

All changes are confined to `fedora/hwmonitor_remote.py`. No new files. The four features are additive (new canvas widgets, new vars, new styling logic) and do not restructure existing data flow. Each feature touches one clearly bounded method.

## Tech Stack

- Python 3.10+, Tkinter, `ttk.Style`, `tk.Canvas`
- No new dependencies

---

## Feature Breakdown

### 1. Summary Cards — Severity Progress Bars

**Affected area:** `_build_ui()` summary card section, `_update_summary_cards()` (or equivalent refresh method)

**What changes:**
- Each of the 4 summary cards (CPU / GPU / Cooling / Drive) gets a `tk.Canvas` progress bar below the value label
- Bar is ~8px tall, full card width
- Fill color: `#37c871` (normal/cool) → `#ffb020` (warn) → `#ff5d5d` (critical)
- Fill width = `value / critical_threshold`, clamped 0.0–1.0
- Thresholds:
  - Temperature: warn 75°C, critical 90°C, bar range 0–90
  - Load %: warn 85, critical 95, bar range 0–100
  - Fan RPM (Cooling): no threshold, bar range 0–3000
  - Drive temp: same as Temperature
- Store canvas refs as `self.summary_bar_canvases: dict[str, tk.Canvas]`
- Redraw bar on every refresh cycle in `_refresh_summary_cards()`

### 2. Detail Chart — Threshold Reference Lines

**Affected area:** `_update_detail_chart()`

**What changes:**
- After the sparkline is drawn, overlay two horizontal dashed lines using `canvas.create_line(..., dash=(4, 3))`
- Amber line at warn threshold Y, red line at critical threshold Y
- Y position computed with the same value→canvas-Y mapping already used for sparkline points
- Only drawn when `sensor_type` has a known threshold (Temperature, Load)
- Lines drawn before the sparkline so they sit behind the data curve

### 3. Filter Toolbar — Active Scope Styling

**Affected area:** `_build_ui()` filter bar, `_apply_quick_scope()`

**What changes:**
- Add `self.scope_buttons: dict[str, ttk.Button]` mapping scope name → button widget
- Active button styled with a highlighted background (`#1a6fa8`) and bright foreground
- Inactive buttons revert to default card style
- `_apply_quick_scope()` calls `_refresh_scope_buttons()` after setting scope
- No layout changes — same 4 buttons (All / Alerts / HWiNFO / Native), same grid positions

### 4. Hardware-Group Toggle

**Affected area:** `_build_ui()` filter bar, `_rebuild_tree()`

**What changes:**
- Add `self.hw_group_var = tk.BooleanVar(value=False)`
- Add `ttk.Checkbutton(filter_bar, text="By HW", variable=self.hw_group_var, command=self._rebuild_tree)` in the filter bar
- In `_rebuild_tree()`: when `hw_group_var` is True, insert only hardware-level nodes into the tree (skip group and sensor children)
- Clicking a hardware node in this mode sets the hardware filter dropdown to that hardware and unchecks the toggle, drilling into it

---

## Testing

All logic under test must be pure static methods on `SensorApp`. No Tkinter in tests.

- Progress bar fill calculation: `_bar_fill(value, sensor_type) -> float` returns 0.0–1.0
- Threshold Y coordinate: already covered by `_history_plot_points` tests; threshold lines use same math
- Scope button state: `_active_scope_button_style(scope, active_scope) -> dict` returns style kwargs
- Hardware group filter: tested via `_rebuild_tree` logic (which has existing indirect coverage)

## Commit Sequence

1. `feat: add severity progress bars to summary cards`
2. `feat: add threshold reference lines to detail chart`
3. `feat: highlight active scope button in filter bar`
4. `feat: add hardware-group toggle to sensor tree`
