# tests/test_alerts.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fedora"))

from hwmonitor_remote import SensorApp, SensorRow


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
