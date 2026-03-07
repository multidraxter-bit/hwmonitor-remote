# tests/test_alerts.py
import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fedora"))

from hwmonitor_remote import AlertEvent, SensorApp, SensorRow


def _row(path: str, sensor_type: str, value: float) -> SensorRow:
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
    new_alerts, new_states = SensorApp._compute_alerts_static([], {})
    assert new_alerts == []
    assert new_states == {}


def test_compute_alerts_new_critical():
    rows = [_row("CPU/Temperatures/Package", "Temperature", 92)]
    new_alerts, new_states = SensorApp._compute_alerts_static(rows, {})
    assert len(new_alerts) == 1
    assert new_alerts[0][0] == "CPU/Temperatures/Package"
    assert new_alerts[0][2] == "critical"


def test_compute_alerts_no_repeat_on_stable():
    rows = [_row("CPU/Temperatures/Package", "Temperature", 92)]
    existing = {"CPU/Temperatures/Package": "critical"}
    new_alerts, _ = SensorApp._compute_alerts_static(rows, existing)
    assert new_alerts == []


def test_compute_alerts_escalation_fires():
    rows = [_row("CPU/Temperatures/Package", "Temperature", 92)]
    existing = {"CPU/Temperatures/Package": "warn"}
    new_alerts, _ = SensorApp._compute_alerts_static(rows, existing)
    assert len(new_alerts) == 1


def test_compute_alerts_recovery_clears():
    rows = [_row("CPU/Temperatures/Package", "Temperature", 60)]
    existing = {"CPU/Temperatures/Package": "critical"}
    _, new_states = SensorApp._compute_alerts_static(rows, existing)
    assert "CPU/Temperatures/Package" not in new_states


def test_matches_severity_filter_active():
    assert SensorApp._matches_severity_filter("critical", "active")
    assert SensorApp._matches_severity_filter("warn", "active")
    assert not SensorApp._matches_severity_filter("cool", "active")


def test_matches_severity_filter_exact():
    assert SensorApp._matches_severity_filter("critical", "critical")
    assert not SensorApp._matches_severity_filter("warn", "critical")


def test_delta_text_rising():
    assert SensorApp._delta_text([70.0, 72.0], "C") == "rising +2 C"


def test_delta_text_falling():
    assert SensorApp._delta_text([72.0, 70.0], "C") == "falling -2 C"


def test_delta_text_steady_with_short_history():
    assert SensorApp._delta_text([70.0], "C") == "steady"


def test_threshold_text_temperature_below_warning():
    app = SensorApp.__new__(SensorApp)
    app.threshold_overrides = {}
    text = app._threshold_text("CPU/Temp", "Temperature", 60, "C")
    assert "15 C below warning" in text
    assert "critical at 90 C" in text


def test_threshold_text_temperature_warning_active():
    app = SensorApp.__new__(SensorApp)
    app.threshold_overrides = {}
    text = app._threshold_text("CPU/Temp", "Temperature", 84, "C")
    assert "warning active" in text
    assert "6 C to critical" in text


def test_threshold_text_temperature_critical():
    app = SensorApp.__new__(SensorApp)
    app.threshold_overrides = {}
    text = app._threshold_text("CPU/Temp", "Temperature", 95, "C")
    assert "critical by +5 C" in text


def test_effective_severity_uses_override_thresholds():
    app = SensorApp.__new__(SensorApp)
    app.threshold_overrides = {"CPU/Temp": {"warn": 70.0, "critical": 80.0}}
    assert app._effective_severity("CPU/Temp", "Temperature", 75.0) == "warn"
    assert app._effective_severity("CPU/Temp", "Temperature", 82.0) == "critical"


def test_top_mover_rows_orders_by_delta():
    app = SensorApp.__new__(SensorApp)
    app.history = {
        "CPU/Temp": [70.0, 76.0],
        "GPU/Temp": [60.0, 62.0],
    }
    app.favorite_paths = {"CPU/Temp"}
    rows = [
        SensorRow(kind="sensor", name="CPU Temp", path="CPU/Temp", indent=0, sensor_type="Temperature", unit="C", value=76.0, severity="warn"),
        SensorRow(kind="sensor", name="GPU Temp", path="GPU/Temp", indent=0, sensor_type="Temperature", unit="C", value=62.0, severity="cool"),
    ]

    movers = app._top_mover_rows(rows)

    assert len(movers) == 2
    assert movers[0].path == "CPU/Temp"
    assert movers[0].detail == "+6 C"


def test_active_alert_rows_only_include_warn_and_critical():
    app = SensorApp.__new__(SensorApp)
    app.muted_paths = set()
    rows = [
        SensorRow(kind="sensor", name="CPU Temp", path="CPU/Temp", indent=0, sensor_type="Temperature", unit="C", value=92.0, severity="critical"),
        SensorRow(kind="sensor", name="GPU Temp", path="GPU/Temp", indent=0, sensor_type="Temperature", unit="C", value=80.0, severity="warn"),
        SensorRow(kind="sensor", name="CPU Load", path="CPU/Load", indent=0, sensor_type="Load", unit="%", value=30.0, severity="cool"),
    ]

    alerts = app._active_alert_rows_from_rows(rows)

    assert [row.path for row in alerts] == ["CPU/Temp", "GPU/Temp"]


def test_record_alert_events_adds_new_entries():
    app = SensorApp.__new__(SensorApp)
    app.alert_history = []
    app._persist_config = lambda: None

    app._record_alert_events([
        ("CPU/Temp", "CPU Temp", "critical", "95 C"),
    ])

    assert len(app.alert_history) == 1
    assert app.alert_history[0].path == "CPU/Temp"
    assert app.alert_history[0].status == "new"


def test_record_alert_events_marks_repeat_and_skips_identical_value():
    app = SensorApp.__new__(SensorApp)
    app._persist_config = lambda: None
    app.alert_history = [
        AlertEvent(timestamp="10:00:00", path="CPU/Temp", name="CPU Temp", severity="critical", value_text="95 C", status="new")
    ]

    app._record_alert_events([
        ("CPU/Temp", "CPU Temp", "critical", "95 C"),
        ("CPU/Temp", "CPU Temp", "critical", "96 C"),
    ])

    assert len(app.alert_history) == 2
    assert app.alert_history[0].value_text == "96 C"
    assert app.alert_history[0].status == "repeat"


def test_history_plot_points_span_canvas():
    points = SensorApp._history_plot_points([10.0, 20.0, 15.0], 100, 50, 10)

    assert len(points) == 3
    assert points[0][0] == 10
    assert round(points[-1][0], 5) == 90
    assert all(10 <= y <= 40 for _, y in points)


def test_wallboard_texts_for_problem_focus():
    title, detail = SensorApp._wallboard_texts(2, 5, "Machine/CPU/Temp", 120)
    assert "Critical 2" in title
    assert "Focus Temp" in title
    assert "Current path: Machine/CPU/Temp" in detail


def test_wallboard_texts_for_stable_system():
    title, detail = SensorApp._wallboard_texts(0, 0, "", 120)
    assert title == "System Stable"
    assert "Monitoring 120 sensors" in detail


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


def test_bar_fill_unknown_sensor_type_returns_zero():
    assert SensorApp._bar_fill(100.0, "Voltage") == 0.0


def test_bar_fill_fan_clamps_above_3000():
    assert SensorApp._bar_fill(6000.0, "Fan") == 1.0


def test_scope_button_style_active():
    assert SensorApp._scope_button_style_name("all", "all") == "Scope.Active.TButton"


def test_scope_button_style_inactive():
    assert SensorApp._scope_button_style_name("active", "all") == "Scope.TButton"


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
