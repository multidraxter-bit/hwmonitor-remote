# UI Compaction & Polish — Design

**Date:** 2026-03-07
**Status:** Approved

---

## Goal

Reclaim ~160px of vertical space from the header and telemetry bar so the sensor tree and detail panel get more room, fix summary card detail truncation, and apply minor visual polish throughout.

## Architecture

All changes are confined to `fedora/hwmonitor_remote.py`. No new files, no new dependencies. Four independently-scoped changes, each touching one bounded area.

---

## Feature Breakdown

### 1. Header Settings Panel (⚙ toggle)

**Affected area:** `_build_ui()` controls grid, new `_toggle_settings_panel()` method, `_persist_config()`, `_load_saved_state()`

**What changes:**
- Add `self.settings_expanded = tk.BooleanVar(value=False)` — persisted to config
- Add a `⚙` button at the far right of Row 0 (after Wallboard), calling `_toggle_settings_panel()`
- Create `self.settings_panel = ttk.Frame(controls, style="Panel.TFrame")` at row 2, columnspan 7
- Move the Preset row (currently Row 1) into `self.settings_panel` at row 0
- Move the SSH settings frame into `self.settings_panel` at row 1 (SSH visibility trace unchanged)
- `_toggle_settings_panel()`: toggles `settings_expanded`, calls `settings_panel.grid()` or `settings_panel.grid_remove()`, updates button text to `⚙` or `✕`
- On startup: `_refresh_ssh_settings_visibility` still fires but now operates within `settings_panel`

**Net gain:** ~96px when collapsed (default state).

### 2. Telemetry Strip

**Affected area:** `_build_ui()` telemetry section, `_refresh_header_summary()`

**What changes:**
- Replace the `telemetry_bar` 4-card grid with a single `ttk.Frame(outer, style="Panel.TFrame", padding=(8, 4))` containing 4 `tk.Label` widgets packed left
- Labels: `[source_health]  │  [snapshot]  │  [focus]  │  [alerts]`
- Add `self.telemetry_strip_alert_label` as a raw `tk.Label` (not ttk) so its `fg` can be set dynamically
- Alert label fg: `#ff5d5d` for critical, `#ffb020` for warn, `#8b9bae` (muted) otherwise
- Separator `│` characters are plain `tk.Label` widgets with muted fg
- `_refresh_header_summary()`: sets 4 individual `tk.StringVar`s (keep existing vars, just re-wire to new labels)

**Net gain:** ~65px.

### 3. Summary Card Detail Truncation Fix

**Affected area:** `_update_overview()` around line 1095

**What changes:**
- Current format: `f"{row.name}  |  {severity}  |  {source_name}  |  {sparkline}"`
- New format: `f"{row.name}  |  {severity}  |  {sparkline}"` — drop `source_name` (redundant; source is visible in the telemetry strip)
- Add `wraplength=160` to the `CardDetail.TLabel` in the card loop so any remaining long text wraps rather than clips
- GPU card still appends `  |  Load {value}` as before

### 4. Visual Polish

**Affected area:** `_build_ui()` padding and style definitions

**What changes:**
- Outer frame padding: `10` → `8`
- Header frame padding: `10` → `8`
- Card frame padding: `10` → `8`
- Treeview row height: `23` → `22`
- Scope button padding: `(10, 6)` → `(8, 4)` on each scope button

---

## State & Config

Two new config keys:
- `"settings_expanded": bool` — persisted so panel stays open/closed across restarts

`_persist_config` and `_load_saved_state` both updated.

---

## Testing

No new unit-testable pure functions are introduced. All changes are layout/display. Manual verification:
- Settings panel starts collapsed; clicking ⚙ expands it; clicking ✕ collapses it
- State survives restart
- SSH rows only appear inside settings panel when URL is `ssh://`
- Telemetry strip shows correct text and alert coloring
- Summary cards no longer truncate on normal 400px left panel width
- All 39 existing tests pass

---

## Commit Sequence

1. `feat: collapse preset and SSH settings behind settings panel toggle`
2. `feat: replace telemetry cards with slim inline strip`
3. `fix: remove source name from summary card detail to prevent truncation`
4. `style: tighten padding and row height throughout`
