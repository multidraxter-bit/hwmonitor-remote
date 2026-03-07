# Dashboard Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add severity progress bars to summary cards, make threshold chart lines visible, highlight the active scope button, and add a hardware-group toggle to the sensor tree.

**Architecture:** All changes are in `fedora/hwmonitor_remote.py` (2,435 lines). No new files. Each feature adds: a static pure helper (unit-testable), an instance state variable, and minimal UI wiring. Tests go in `tests/test_alerts.py`.

**Tech Stack:** Python 3.10+, Tkinter, ttk.Style, tk.Canvas, pytest

---

## Task 1: Summary Card Progress Bars

**Files:**
- Modify: `fedora/hwmonitor_remote.py` (lines 110–111, 308–323, 978–1037)
- Test: `tests/test_alerts.py`

The 4 summary cards (CPU / GPU / Cooling / Drive) currently show text only. We add an 8px canvas bar under each card's detail label. Fill fraction = value ÷ critical threshold, clamped 0–1. Color tracks severity.

---

### Step 1: Write the failing tests

Append to `tests/test_alerts.py`:

```python
import pytest


def test_bar_fill_temperature_normal():
    assert SensorApp._bar_fill(45.0, "Temperature") == pytest.approx(45.0 / 90.0)


def test_bar_fill_temperature_clamps_at_one():
    assert SensorApp._bar_fill(100.0, "Temperature") == 1.0


def test_bar_fill_none_returns_zero():
    assert SensorApp._bar_fill(None, "Temperature") == 0.0


def test_bar_fill_fan_uses_3000_max():
    assert SensorApp._bar_fill(1500.0, "Fan") == pytest.approx(0.5)


def test_bar_fill_load():
    assert SensorApp._bar_fill(50.0, "Load") == pytest.approx(50.0 / 95.0)


def test_bar_color_severity():
    assert SensorApp._bar_color("warn") == "#ffb020"
    assert SensorApp._bar_color("critical") == "#ff5d5d"
    assert SensorApp._bar_color("cool") == "#37c871"
    assert SensorApp._bar_color("normal") == "#37c871"
```

### Step 2: Run tests to confirm they fail

```bash
python -m pytest tests/test_alerts.py::test_bar_fill_temperature_normal -v
```

Expected: `FAILED` — `AttributeError: type object 'SensorApp' has no attribute '_bar_fill'`

### Step 3: Add `_bar_fill` and `_bar_color` static methods

Find `_default_thresholds` at line ~2167 and add these two methods directly after it:

```python
@staticmethod
def _bar_fill(value: float | None, sensor_type: str) -> float:
    """Return 0.0–1.0 fill fraction for a summary card progress bar."""
    if value is None:
        return 0.0
    if sensor_type == "Fan":
        return min(value / 3000.0, 1.0)
    thresholds = SensorApp._default_thresholds(sensor_type)
    if thresholds is None:
        return 0.0
    return min(value / thresholds["critical"], 1.0)

@staticmethod
def _bar_color(severity: str) -> str:
    """Return progress bar fill color for a given severity string."""
    return {"warn": "#ffb020", "critical": "#ff5d5d"}.get(severity, "#37c871")
```

### Step 4: Run tests to confirm they pass

```bash
python -m pytest tests/test_alerts.py -k "bar_fill or bar_color" -v
```

Expected: all 7 tests PASS.

### Step 5: Add `self.summary_bar_canvases` to `__init__`

Find line ~111 where `self.summary_detail_vars` is declared. Add directly after it:

```python
self.summary_bar_canvases: dict[str, tk.Canvas] = {}
```

### Step 6: Add canvas bars to the summary card build loop

In `_build_ui`, find the summary card loop (lines ~308–323). The loop body currently ends with:
```python
            self.summary_value_vars[title] = value_var
            self.summary_detail_vars[title] = detail_var
```

Add these three lines immediately after:
```python
            bar_canvas = tk.Canvas(card_frame, height=6, bg="#27313c", highlightthickness=0, bd=0)
            bar_canvas.pack(fill="x", pady=(6, 0))
            self.summary_bar_canvases[title] = bar_canvas
```

### Step 7: Add `_redraw_summary_bar` method

Add this method to `SensorApp`, near `_update_overview`:

```python
def _redraw_summary_bar(self, name: str, row: "SensorRow | None") -> None:
    canvas = self.summary_bar_canvases.get(name)
    if canvas is None:
        return
    canvas.delete("all")
    w = canvas.winfo_width() or int(canvas.cget("width"))
    h = int(canvas.cget("height"))
    canvas.create_rectangle(0, 0, w, h, fill="#27313c", outline="")
    if row is None or row.value is None:
        return
    fill = SensorApp._bar_fill(row.value, row.sensor_type)
    color = SensorApp._bar_color(row.severity)
    bar_w = max(int(w * fill), 0)
    if bar_w > 0:
        canvas.create_rectangle(0, 0, bar_w, h, fill=color, outline="")
```

### Step 8: Call `_redraw_summary_bar` from `_update_overview`

In `_update_overview`, find the loop at lines ~1027–1037:

```python
        for name, row in summaries.items():
            if row:
                self.summary_value_vars[name].set(self._value_text(row))
                ...
                self.summary_detail_vars[name].set(detail)
            else:
                self.summary_value_vars[name].set("--")
                self.summary_detail_vars[name].set("No sensor")
```

Add `self._redraw_summary_bar(name, row)` as the last line inside both the `if row:` and `else:` branches:

```python
        for name, row in summaries.items():
            if row:
                self.summary_value_vars[name].set(self._value_text(row))
                source_name = self._source_for_path(row.path)
                detail = f"{row.name}  |  {SensorApp._severity_text(row.severity)}  |  {source_name}  |  {self._history_text(row.path)}"
                if name == "GPU" and gpu_load:
                    detail += f"  |  Load {self._value_text(gpu_load)}"
                self.summary_detail_vars[name].set(detail)
                self._redraw_summary_bar(name, row)
            else:
                self.summary_value_vars[name].set("--")
                self.summary_detail_vars[name].set("No sensor")
                self._redraw_summary_bar(name, None)
```

### Step 9: Run full test suite

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

### Step 10: Commit

```bash
git add fedora/hwmonitor_remote.py tests/test_alerts.py
git commit -m "feat: add severity progress bars to summary cards"
```

---

## Task 2: Make Threshold Lines Visible on Detail Chart

**Files:**
- Modify: `fedora/hwmonitor_remote.py` (lines ~2123–2124)

The threshold lines already exist in `_draw_detail_chart` but use near-black colors (`#7c5c00`, `#7c2020`) that are invisible against the dark background. Change to the app's standard severity palette.

---

### Step 1: Find the threshold line colors

In `_draw_detail_chart` (around line 2122), find:

```python
        for value, color in (
            (thresholds.get("warn"), "#7c5c00"),
            (thresholds.get("critical"), "#7c2020"),
        ):
```

### Step 2: Replace with visible colors

```python
        for value, color in (
            (thresholds.get("warn"), "#ffb020"),
            (thresholds.get("critical"), "#ff5d5d"),
        ):
```

No tests needed — this is a pure color-string change with no logic.

### Step 3: Run test suite to confirm nothing broken

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

### Step 4: Commit

```bash
git add fedora/hwmonitor_remote.py
git commit -m "feat: make threshold reference lines visible on detail chart"
```

---

## Task 3: Active Scope Button Highlighting

**Files:**
- Modify: `fedora/hwmonitor_remote.py` (lines ~93–155 for `__init__`, ~167–211 for styles, ~408–418 for filter bar, ~605–629 for `_apply_quick_scope`)
- Test: `tests/test_alerts.py`

The 4 quick-scope buttons (All / Alerts / HWiNFO / Native) have no active-state indicator. We track which scope is active and restyle the active button with a blue tint.

---

### Step 1: Write the failing test

Append to `tests/test_alerts.py`:

```python
def test_scope_button_style_active():
    assert SensorApp._scope_button_style_name("all", "all") == "Scope.Active.TButton"


def test_scope_button_style_inactive():
    assert SensorApp._scope_button_style_name("active", "all") == "Scope.TButton"
```

### Step 2: Run tests to confirm they fail

```bash
python -m pytest tests/test_alerts.py::test_scope_button_style_active -v
```

Expected: `FAILED` — `AttributeError: type object 'SensorApp' has no attribute '_scope_button_style_name'`

### Step 3: Add `_scope_button_style_name` static method

Add near the other small static helpers (e.g., after `_bar_color`):

```python
@staticmethod
def _scope_button_style_name(scope: str, active_scope: str) -> str:
    """Return the ttk style name for a scope button given the currently active scope."""
    return "Scope.Active.TButton" if scope == active_scope else "Scope.TButton"
```

### Step 4: Run tests to confirm they pass

```bash
python -m pytest tests/test_alerts.py -k "scope_button" -v
```

Expected: 2 PASS.

### Step 5: Add `self.scope_buttons` and `self.active_scope` to `__init__`

Find the block of instance variable declarations in `__init__` (around line 107). Add:

```python
self.scope_buttons: dict[str, ttk.Button] = {}
self.active_scope: str = "all"
```

### Step 6: Add the two ttk styles in `_build_ui`

In `_build_ui`, find where styles are configured (around line 206 where `"TButton"` is configured):

```python
        style.configure("TButton", background=card, foreground=text, bordercolor=edge)
```

Add two new scope-specific styles directly after:

```python
        style.configure("Scope.TButton", background=card, foreground=muted, bordercolor=edge)
        style.configure("Scope.Active.TButton", background="#1a5e8c", foreground=text, bordercolor="#2a8fc7")
        style.map("Scope.Active.TButton", background=[("active", "#1a6fa8")])
```

### Step 7: Capture scope button refs in the filter bar

In `_build_ui`, find the 4 quick-scope button creations (around lines 414–417):

```python
        ttk.Button(filter_bar, text="All", command=lambda: self._apply_quick_scope("all")).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(filter_bar, text="Alerts", command=lambda: self._apply_quick_scope("active")).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(filter_bar, text="HWiNFO", command=lambda: self._apply_quick_scope("hwinfo")).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(filter_bar, text="Native", command=lambda: self._apply_quick_scope("native")).grid(row=0, column=5, padx=(0, 12))
```

Replace with:

```python
        for scope_key, scope_label, col in (("all", "All", 2), ("active", "Alerts", 3), ("hwinfo", "HWiNFO", 4), ("native", "Native", 5)):
            _pad = (0, 6) if scope_key != "native" else (0, 12)
            btn = ttk.Button(filter_bar, text=scope_label, style="Scope.Active.TButton" if scope_key == "all" else "Scope.TButton",
                             command=lambda s=scope_key: self._apply_quick_scope(s))
            btn.grid(row=0, column=col, padx=_pad)
            self.scope_buttons[scope_key] = btn
```

### Step 8: Add `_refresh_scope_buttons` method

Add this method to `SensorApp`:

```python
def _refresh_scope_buttons(self, active_scope: str) -> None:
    self.active_scope = active_scope
    for scope, btn in self.scope_buttons.items():
        btn.configure(style=SensorApp._scope_button_style_name(scope, active_scope))
```

### Step 9: Call `_refresh_scope_buttons` from `_apply_quick_scope`

Find `_apply_quick_scope` (line ~605). At the very end of the method, before `self._rebuild_tree()`:

```python
        self._refresh_scope_buttons(scope)
        self._rebuild_tree()
```

### Step 10: Run full test suite

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

### Step 11: Commit

```bash
git add fedora/hwmonitor_remote.py tests/test_alerts.py
git commit -m "feat: highlight active scope button in filter bar"
```

---

## Task 4: Hardware-Group Toggle ("By HW")

**Files:**
- Modify: `fedora/hwmonitor_remote.py` (lines ~107–155 for `__init__`, ~408–441 for filter bar, ~1104–1124 for `_rebuild_tree`)
- Test: `tests/test_alerts.py`

A "By HW" checkbutton collapses the tree to show only top-level hardware nodes. Double-clicking a hardware node drills into it (sets the hardware filter and unchecks the toggle).

---

### Step 1: Write the failing tests

Append to `tests/test_alerts.py`:

```python
def test_hardware_names_from_payload_returns_hardware_nodes():
    payload = {
        "kind": "machine",
        "name": "PC",
        "children": [
            {"kind": "hardware", "name": "Intel CPU", "children": []},
            {"kind": "hardware", "name": "NVIDIA GPU", "children": []},
        ],
    }
    assert SensorApp._hardware_names_from_payload(payload) == ["Intel CPU", "NVIDIA GPU"]


def test_hardware_names_from_payload_excludes_non_hardware():
    payload = {
        "kind": "machine",
        "children": [
            {"kind": "group", "name": "Temperatures"},
            {"kind": "hardware", "name": "CPU"},
        ],
    }
    assert SensorApp._hardware_names_from_payload(payload) == ["CPU"]


def test_hardware_names_from_payload_empty():
    assert SensorApp._hardware_names_from_payload({}) == []
```

### Step 2: Run tests to confirm they fail

```bash
python -m pytest tests/test_alerts.py::test_hardware_names_from_payload_returns_hardware_nodes -v
```

Expected: `FAILED` — `AttributeError: type object 'SensorApp' has no attribute '_hardware_names_from_payload'`

### Step 3: Add `_hardware_names_from_payload` static method

Add near the other static helpers:

```python
@staticmethod
def _hardware_names_from_payload(payload: dict) -> list[str]:
    """Return names of direct hardware-kind children of a machine payload node."""
    return [child["name"] for child in payload.get("children", []) if child.get("kind") == "hardware"]
```

### Step 4: Run tests to confirm they pass

```bash
python -m pytest tests/test_alerts.py -k "hardware_names" -v
```

Expected: 3 PASS.

### Step 5: Add `self.hw_group_var` to `__init__`

Find the BooleanVar declarations in `__init__` (around line 98 where `wallboard_mode_var` and `compact_mode_var` are). Add:

```python
self.hw_group_var = tk.BooleanVar(value=False)
```

### Step 6: Add the "By HW" checkbutton to the filter bar

In `_build_ui`, find the filter bar's second row (around line 436):

```python
        ttk.Checkbutton(filter_bar, text="Compact", variable=self.compact_mode_var, command=self._rebuild_tree).grid(row=1, column=8, padx=(0, 8), pady=(8, 0))
```

Add directly after it:

```python
        ttk.Checkbutton(filter_bar, text="By HW", variable=self.hw_group_var, command=self._rebuild_tree).grid(row=1, column=9, padx=(0, 8), pady=(8, 0))
```

Then shift all subsequent column numbers up by 1 (Expand → col 10, Collapse → col 11, Reset → col 12, Export CSV → col 13).

### Step 7: Add `_insert_hw_group_tree` method

Add this method to `SensorApp`:

```python
def _insert_hw_group_tree(self) -> None:
    """Insert only hardware-level nodes into the tree (no groups or sensors)."""
    for child in self.current_payload.get("children", []):
        if child.get("kind") != "hardware":
            continue
        name = child.get("name", "Unknown")
        item = self.tree.insert("", "end", text=name, values=("", "", "", ""), tags=("hardware",))
        self.item_paths[item] = name
        self.item_nodes[item] = child
        self.visible_group_count += 1
```

### Step 8: Branch in `_rebuild_tree` for HW group mode

In `_rebuild_tree` (line ~1104), find the line:

```python
        self._insert_tree_node("", self.current_payload, search, category, 0, "")
```

Replace the entire block from `search = ...` to `self._insert_tree_node(...)` with:

```python
        if self.hw_group_var.get():
            self._insert_hw_group_tree()
        else:
            search = self.search_var.get().strip().lower()
            category = self.category_var.get() or "all"
            self._insert_tree_node("", self.current_payload, search, category, 0, "")
```

### Step 9: Add `_drill_into_selected_hardware` and wire the double-click

Add this method to `SensorApp`:

```python
def _drill_into_selected_hardware(self) -> None:
    """When in HW group mode, double-clicking a hardware node drills into it."""
    selection = self.tree.selection()
    if not selection:
        return
    item_id = selection[0]
    node = self.item_nodes.get(item_id, {})
    if node.get("kind") != "hardware":
        return
    self.hardware_var.set(node.get("name", "all"))
    self.hw_group_var.set(False)
    self._rebuild_tree()
```

In `_build_ui`, find the tree's `<Double-1>` binding:

```python
        self.tree.bind("<Double-1>", self._toggle_selected_favorite)
```

Replace with a dispatcher:

```python
        self.tree.bind("<Double-1>", self._on_tree_double_click)
```

Add the dispatcher method:

```python
def _on_tree_double_click(self, _event=None) -> None:
    if self.hw_group_var.get():
        self._drill_into_selected_hardware()
    else:
        self._toggle_selected_favorite()
```

### Step 10: Run full test suite

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

### Step 11: Run lint and type check

```bash
python -m flake8 fedora/hwmonitor_remote.py
python -m mypy fedora/hwmonitor_remote.py --ignore-missing-imports
```

Expected: no new errors.

### Step 12: Commit

```bash
git add fedora/hwmonitor_remote.py tests/test_alerts.py
git commit -m "feat: add hardware-group toggle to sensor tree"
```

---

## Done

Run the app to verify all four features work visually:

```bash
python fedora/hwmonitor_remote.py
```

Check:
1. Summary cards show colored progress bars that update each refresh cycle
2. Detail chart threshold lines are clearly visible in amber and red
3. The active scope button (All/Alerts/HWiNFO/Native) is highlighted blue
4. "By HW" checkbox collapses tree to hardware nodes; double-click drills in
