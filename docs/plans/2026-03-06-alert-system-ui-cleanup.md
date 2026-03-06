# Alert System + UI Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove redundant dashboard and favorites panels to reduce clutter, collapse the detail pane when empty, and add an in-app alert banner plus optional system tray desktop notifications.

**Architecture:** All primary changes are in `fedora/hwmonitor_remote.py`. UI cleanup removes `dashboard_bar` and `favorites_bar` frames and their associated state/methods. The detail pane is hidden until a sensor is selected. The alert system adds an `alert_states` dict, a `_compute_alerts()` method for pure logic, and a `_check_and_fire_alerts()` method that drives both the in-app banner and pystray desktop notifications.

**Tech Stack:** Python 3.11+, tkinter, pystray (optional, graceful fallback), Pillow (optional, same fallback)

---

### Task 1: Remove dashboard_bar and favorites_bar

**Files:**
- Modify: `fedora/hwmonitor_remote.py`

The `dashboard_bar` (CPU Live / GPU Live / Storage Live cards) and `favorites_bar` (inline label strip) both duplicate data already shown in the left overview panel.

**Step 1: Remove dashboard state from `__init__`**

In `SensorApp.__init__`, delete these two lines (around line 48-51):

```python
# DELETE these:
self.dashboard_value_vars: dict[str, tk.StringVar] = {}
self.dashboard_detail_vars: dict[str, tk.StringVar] = {}
```

**Step 2: Remove dashboard_bar and favorites_bar from `_build_ui`**

Find and delete the `dashboard_bar` block (starts with `dashboard_bar = ttk.Frame(explorer, ...)`), which creates and grids three "CPU Live / GPU Live / Storage Live" cards.

Find and delete the `favorites_bar` block (starts with `favorites_bar = ttk.Frame(explorer, style="Card.TFrame", padding=6)`), which creates `self.favorite_label`.

**Step 3: Remove dashboard updates from `_update_overview`**

In `_update_overview`, delete the `dashboard` dict and the for-loop that sets `self.dashboard_value_vars` / `self.dashboard_detail_vars`.

Also delete the `favorites_bar` label update line:
```python
# DELETE:
self.favorite_label.configure(text=...)
```

**Step 4: Remove now-unused methods**

Delete `_compose_dashboard_text` and `_badge_for_row` — they are only called from the deleted dashboard code.

**Step 5: Run the app to verify it starts without errors**

```bash
cd /home/loofi/hwremote-monitor
python fedora/hwmonitor_remote.py --url ssh://loofi@192.168.1.3
```

Expected: Window opens. Left panel shows summary cards and favorites. Right panel shows only filter bar, sensor tree, and detail pane. No dashboard cards, no favorites label strip.

**Step 6: Commit**

```bash
git add fedora/hwmonitor_remote.py
git commit -m "refactor: remove redundant dashboard and favorites bar panels"
```

---

### Task 2: Collapsible detail pane

**Files:**
- Modify: `fedora/hwmonitor_remote.py`

Currently `detail_frame` is always packed, showing placeholder text even when nothing is selected.

**Step 1: Store a reference to the detail frame and unpack it initially**

In `_build_ui`, after creating `detail_frame`, replace:
```python
detail_frame = ttk.Frame(explorer, style="Card.TFrame", padding=8)
detail_frame.pack(fill="x", pady=(8, 0))
```
with:
```python
self.detail_frame = ttk.Frame(explorer, style="Card.TFrame", padding=8)
# Don't pack yet — will be shown on first selection
```

Update all references inside `_build_ui` from `detail_frame` to `self.detail_frame`.

**Step 2: Show the detail frame on sensor selection**

In `_on_tree_select`, at the start of the branch where `kind == "sensor"`, add:
```python
self.detail_frame.pack(fill="x", pady=(8, 0))
```

**Step 3: Hide the detail frame when selection is cleared**

In `_on_tree_select`, inside the `if not selection:` branch, add:
```python
self.detail_frame.pack_forget()
```

**Step 4: Run the app and verify**

```bash
python fedora/hwmonitor_remote.py
```

Expected: Detail pane is invisible on launch. Clicking a sensor makes it appear. Pressing Escape or clicking away hides it again (or it stays visible — selecting a non-sensor item like a group should also hide it; add `self.detail_frame.pack_forget()` in the `else` branch of the sensor/non-sensor check).

**Step 5: Commit**

```bash
git add fedora/hwmonitor_remote.py
git commit -m "feat: collapse detail pane when no sensor is selected"
```

---

### Task 3: Alert logic + unit tests

**Files:**
- Create: `tests/test_alerts.py`
- Modify: `fedora/hwmonitor_remote.py`

This task introduces the alert state transition logic as a pure, testable method before wiring it to the UI.

**Step 1: Create the test file**

```python
# tests/test_alerts.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fedora"))

from hwmonitor_remote import SensorApp, SensorRow

SEVERITY_ORDER = {"normal": 0, "cool": 0, "warn": 1, "critical": 2}


def make_row(path, sensor_type, value):
    return SensorRow(
        kind="sensor",
        name=path.split("/")[-1],
        path=path,
        indent=0,
        sensor_type=sensor_type,
        value=value,
        unit="C" if sensor_type == "Temperature" else "%",
        category="temperature" if sensor_type == "Temperature" else "load",
        severity=SensorApp._severity_for(sensor_type, value),
    )


def test_severity_temperature_normal():
    assert SensorApp._severity_for("Temperature", 60) == "cool"

def test_severity_temperature_warn():
    assert SensorApp._severity_for("Temperature", 80) == "warn"

def test_severity_temperature_critical():
    assert SensorApp._severity_for("Temperature", 92) == "critical"

def test_severity_load_warn():
    assert SensorApp._severity_for("Load", 85) == "warn"

def test_severity_load_critical():
    assert SensorApp._severity_for("Load", 96) == "critical"

def test_compute_alerts_empty():
    assert SensorApp._compute_alerts_static([], {}) == ([], {})

def test_compute_alerts_new_critical():
    rows = [make_row("CPU/Temperatures/Package", "Temperature", 92)]
    new_alerts, new_states = SensorApp._compute_alerts_static(rows, {})
    assert len(new_alerts) == 1
    assert new_alerts[0][0] == "CPU/Temperatures/Package"
    assert new_alerts[0][2] == "critical"

def test_compute_alerts_no_repeat_on_stable():
    rows = [make_row("CPU/Temperatures/Package", "Temperature", 92)]
    existing = {"CPU/Temperatures/Package": "critical"}
    new_alerts, _ = SensorApp._compute_alerts_static(rows, existing)
    assert new_alerts == []  # no new notification, already known

def test_compute_alerts_escalation_fires():
    rows = [make_row("CPU/Temperatures/Package", "Temperature", 92)]
    existing = {"CPU/Temperatures/Package": "warn"}
    new_alerts, _ = SensorApp._compute_alerts_static(rows, existing)
    assert len(new_alerts) == 1  # escalated from warn to critical

def test_compute_alerts_recovery_clears():
    rows = [make_row("CPU/Temperatures/Package", "Temperature", 60)]
    existing = {"CPU/Temperatures/Package": "critical"}
    _, new_states = SensorApp._compute_alerts_static(rows, existing)
    assert "CPU/Temperatures/Package" not in new_states
```

**Step 2: Run tests to confirm they all fail**

```bash
cd /home/loofi/hwremote-monitor
python -m pytest tests/test_alerts.py -v
```

Expected: All tests fail — `_severity_for` and `_compute_alerts_static` don't exist yet.

**Step 3: Add `_severity_for` static method to `SensorApp`**

Refactor the existing `_severity` static method. Add a new `_severity_for(sensor_type, value)` that takes plain args (testable without a node dict), and update `_severity` to call it:

```python
@staticmethod
def _severity_for(sensor_type: str, value: float | None) -> str:
    if value is None:
        return "normal"
    if sensor_type == "Temperature":
        if value >= 90:
            return "critical"
        if value >= 75:
            return "warn"
        return "cool"
    if sensor_type in {"Load", "Control"}:
        if value >= 95:
            return "critical"
        if value >= 80:
            return "warn"
        return "cool"
    if sensor_type == "Power":
        if value >= 300:
            return "critical"
        if value >= 220:
            return "warn"
    return "normal"

@staticmethod
def _severity(node: dict | SensorRow) -> str:
    if isinstance(node, SensorRow):
        return SensorApp._severity_for(node.sensor_type, node.value)
    return SensorApp._severity_for(node.get("type", ""), node.get("value"))
```

**Step 4: Add `_compute_alerts_static` static method to `SensorApp`**

```python
_SEVERITY_ORDER = {"normal": 0, "cool": 0, "warn": 1, "critical": 2}

@staticmethod
def _compute_alerts_static(
    rows: list["SensorRow"],
    existing_states: dict[str, str],
) -> tuple[list[tuple[str, str, str, str]], dict[str, str]]:
    """
    Returns (new_alerts, updated_states).
    new_alerts: list of (path, name, severity, value_text) for sensors that worsened.
    updated_states: new alert_states dict (only contains warn/critical sensors).
    """
    new_alerts: list[tuple[str, str, str, str]] = []
    new_states: dict[str, str] = {}
    order = SensorApp._SEVERITY_ORDER

    for row in rows:
        if row.kind != "sensor" or row.value is None:
            continue
        severity = SensorApp._severity_for(row.sensor_type, row.value)
        if severity in ("warn", "critical"):
            new_states[row.path] = severity
            prev = existing_states.get(row.path, "normal")
            if order[severity] > order[prev]:
                value_text = SensorApp._format_value(row.value, row.unit)
                new_alerts.append((row.path, row.name, severity, value_text))

    return new_alerts, new_states
```

**Step 5: Add `self.alert_states` to `__init__`**

```python
self.alert_states: dict[str, str] = {}
```

**Step 6: Run tests to confirm they pass**

```bash
python -m pytest tests/test_alerts.py -v
```

Expected: All 9 tests pass.

**Step 7: Commit**

```bash
git add tests/test_alerts.py fedora/hwmonitor_remote.py
git commit -m "feat: add alert state tracking logic with unit tests"
```

---

### Task 4: In-app alert banner

**Files:**
- Modify: `fedora/hwmonitor_remote.py`

**Step 1: Add banner frame in `_build_ui`**

Just after the `header` frame is packed and before `body = ttk.Panedwindow(...)`, add:

```python
self.alert_banner = tk.Frame(outer, bg="#7c2020", padx=10, pady=6)
# Not packed by default — shown only when alerts exist

self.alert_text_var = tk.StringVar()
alert_label = tk.Label(
    self.alert_banner,
    textvariable=self.alert_text_var,
    bg="#7c2020",
    fg="#ffffff",
    font=("DejaVu Sans", 10, "bold"),
    anchor="w",
)
alert_label.pack(side="left", fill="x", expand=True)

alert_dismiss = tk.Button(
    self.alert_banner,
    text="x",
    bg="#7c2020",
    fg="#ffffff",
    relief="flat",
    font=("DejaVu Sans", 10),
    command=self._dismiss_alert_banner,
)
alert_dismiss.pack(side="right")
self._banner_dismissed = False
```

**Step 2: Add `_dismiss_alert_banner` method**

```python
def _dismiss_alert_banner(self) -> None:
    self._banner_dismissed = True
    self.alert_banner.pack_forget()
```

**Step 3: Add `_update_alert_banner` method**

```python
def _update_alert_banner(self, rows: list[SensorRow]) -> None:
    breached = [
        row for row in rows
        if row.kind == "sensor" and row.value is not None
        and SensorApp._severity_for(row.sensor_type, row.value) in ("warn", "critical")
    ]
    if not breached:
        self.alert_banner.pack_forget()
        self._banner_dismissed = False
        return

    if self._banner_dismissed:
        return

    parts = [f"{row.name} {self._format_value(row.value, row.unit)}" for row in breached[:5]]
    if len(breached) > 5:
        parts.append(f"+{len(breached) - 5} more")

    # Use red for any critical, amber for warn-only
    has_critical = any(
        SensorApp._severity_for(r.sensor_type, r.value) == "critical" for r in breached
    )
    color = "#7c2020" if has_critical else "#7c5c00"
    self.alert_banner.configure(bg=color)
    for widget in self.alert_banner.winfo_children():
        try:
            widget.configure(bg=color)
        except tk.TclError:
            pass

    self.alert_text_var.set("  ALERT:  " + "  |  ".join(parts))
    self.alert_banner.pack(fill="x", pady=(4, 0), before=self.body)
```

**Step 4: Call `_update_alert_banner` from `_apply_data`**

In `_apply_data`, after `self._rebuild_tree()`, add:

```python
rows = self._flatten_rows(payload)
self._update_alert_banner(rows)
```

**Step 5: Run the app and manually trigger a test**

```bash
python fedora/hwmonitor_remote.py
```

To test without a live connection, temporarily add this to `_apply_data` before calling `_update_alert_banner`:

```python
# TEMP TEST — remove after verifying
from hwmonitor_remote import SensorRow
rows = [SensorRow(kind="sensor", name="CPU Package", path="x", indent=0,
                  sensor_type="Temperature", value=95, unit="C",
                  category="temperature", severity="critical")]
self._update_alert_banner(rows)
```

Expected: Red banner appears below the header reading `ALERT:  CPU Package 95 C`. Dismiss button hides it.

Remove the temp test code after verifying.

**Step 6: Commit**

```bash
git add fedora/hwmonitor_remote.py
git commit -m "feat: add in-app alert banner for warn/critical sensors"
```

---

### Task 5: System tray integration (pystray)

**Files:**
- Modify: `fedora/hwmonitor_remote.py`

**Step 1: Add optional pystray import at the top of the file**

```python
try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False
```

**Step 2: Add `_create_tray_icon_image` static method**

Creates a simple 64x64 icon using Pillow (a colored circle):

```python
@staticmethod
def _create_tray_icon_image(color: str = "#37c871") -> "Image.Image":
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img
```

**Step 3: Add `_setup_tray` method**

```python
def _setup_tray(self) -> None:
    if not _TRAY_AVAILABLE:
        return

    def on_open(icon, item):
        icon.stop()
        self.root.after(0, self._restore_from_tray)

    def on_refresh(icon, item):
        self.root.after(0, self.refresh)

    def on_quit(icon, item):
        icon.stop()
        self.root.after(0, self.root.destroy)

    menu = pystray.Menu(
        pystray.MenuItem("Open", on_open, default=True),
        pystray.MenuItem("Refresh", on_refresh),
        pystray.MenuItem("Quit", on_quit),
    )
    self._tray_icon = pystray.Icon(
        "hwmonitor-remote",
        self._create_tray_icon_image(),
        "HWMonitor Remote",
        menu,
    )
    self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
    self._tray_thread.start()
```

**Step 4: Add `_minimize_to_tray` and `_restore_from_tray` methods**

```python
def _minimize_to_tray(self) -> None:
    if not _TRAY_AVAILABLE or not hasattr(self, "_tray_icon"):
        return
    self.root.withdraw()

def _restore_from_tray(self) -> None:
    self.root.deiconify()
    self.root.lift()
    self.root.focus_force()
    # Restart tray icon since it stopped
    self._setup_tray()
```

**Step 5: Override window minimize behavior**

In `__init__`, after `self._build_ui()`, add:

```python
self._setup_tray()
self.root.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
```

**Step 6: Add `_send_tray_notification` method**

```python
def _send_tray_notification(self, title: str, message: str, critical: bool = False) -> None:
    if not _TRAY_AVAILABLE or not hasattr(self, "_tray_icon"):
        return
    color = "#ff5d5d" if critical else "#ffb020"
    self._tray_icon.icon = self._create_tray_icon_image(color)
    # pystray notify is not available on all platforms; wrap in try
    try:
        self._tray_icon.notify(message, title)
    except Exception:
        pass
```

**Step 7: Wire notifications into refresh cycle via `_check_and_fire_alerts`**

Add this method:

```python
def _check_and_fire_alerts(self, rows: list[SensorRow]) -> None:
    new_alerts, new_states = SensorApp._compute_alerts_static(rows, self.alert_states)
    self.alert_states = new_states
    for _path, name, severity, value_text in new_alerts:
        is_critical = severity == "critical"
        self._send_tray_notification(
            title=f"HWMonitor: {severity.upper()}",
            message=f"{name}: {value_text}",
            critical=is_critical,
        )
```

**Step 8: Call `_check_and_fire_alerts` from `_apply_data`**

In `_apply_data`, after `rows = self._flatten_rows(payload)`, add:

```python
self._check_and_fire_alerts(rows)
```

**Step 9: Run the app and verify tray behavior**

```bash
pip install pystray Pillow
python fedora/hwmonitor_remote.py
```

Expected:
- App appears in system tray.
- Clicking the X button on the window hides it to tray.
- Right-clicking tray icon shows Open / Refresh / Quit.
- "Open" restores the window.

If pystray is not installed, app should start and function normally without tray.

**Step 10: Commit**

```bash
git add fedora/hwmonitor_remote.py
git commit -m "feat: add system tray integration with desktop notifications"
```

---

### Task 6: Update RPM spec and README

**Files:**
- Modify: `packaging/rpm/hwmonitor-remote.spec`
- Modify: `README.md`

**Step 1: Add weak dependencies to the RPM spec**

In `hwmonitor-remote.spec`, add after the `Requires:` lines:

```spec
Recommends:     python3-pillow
Recommends:     python3-pystray
```

(`Recommends` in RPM = weak/optional dependency — installed by default but not required.)

**Step 2: Add tray deps note to README**

In `README.md`, add a section under the launch instructions:

```markdown
## Optional: system tray and desktop notifications

Install `pystray` and `Pillow` for tray icon and desktop alert notifications:

```bash
pip install pystray Pillow
```

Without these, the app works normally without tray support.
```

**Step 3: Commit**

```bash
git add packaging/rpm/hwmonitor-remote.spec README.md
git commit -m "docs: note optional pystray/Pillow deps for tray notifications"
```

---

### Task 7: Final smoke test and push

**Step 1: Run the full test suite**

```bash
cd /home/loofi/hwremote-monitor
python -m pytest tests/ -v
```

Expected: All 9 tests pass.

**Step 2: Run the app end-to-end**

```bash
python fedora/hwmonitor_remote.py
```

Verify:
- No `dashboard_bar`, no `favorites_bar` in the right pane
- Detail pane hidden on launch, appears when selecting a sensor
- Alert banner appears for any warn/critical sensor
- Tray icon visible; minimize-to-tray works
- Desktop notification fires when a sensor escalates severity

**Step 3: Push to origin**

```bash
git push origin main
```
