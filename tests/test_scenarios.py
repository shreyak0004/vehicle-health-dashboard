"""Tests for vehicle simulation scenarios without altering production database."""
from datetime import datetime
import random
import pytest

from ingestion.simulator import generate_trip, generate_history


def test_overheating_scenario():
    readings, events, final_soc, _ = generate_trip(
        rng=random.Random(42),
        start_time=datetime(2026, 10, 13, 18, 0),
        duration_min=60,
        mode="highway",
        soc=90.0,
        odometer=12000.0,
        ambient=25.0,
        eff_factor=1.0,
        overheat=True,
    )

    overheat_events = [e for e in events if e[2] == "BATTERY_OVERHEAT_WARNING"]
    max_temp = max(row[3] for row in readings)

    assert len(readings) == 60, f"Expected exactly 60 readings for 60 min trip, got {len(readings)}"
    assert len(set(row[1] for row in readings)) == 60, "Duplicate timestamps detected in readings"
    assert max_temp >= 55.0, f"Expected overheating temp >= 55C, got {max_temp}"
    assert len(overheat_events) >= 1, "Expected at least 1 BATTERY_OVERHEAT_WARNING event"


def test_low_battery_scenario():
    readings, events, final_soc, _ = generate_trip(
        rng=random.Random(42),
        start_time=datetime(2026, 10, 19, 8, 0),
        duration_min=35,
        mode="city",
        soc=90.0,
        odometer=12000.0,
        ambient=20.0,
        eff_factor=1.0,
        low_battery=True,
    )

    low_battery_events = [e for e in events if e[2] == "LOW_BATTERY_WARNING"]

    assert len(readings) == 35, f"Expected 35 readings, got {len(readings)}"
    assert all(row[4] <= 15.0 for row in readings), "All SOC readings should be <= 15% when low_battery=True"
    assert len(low_battery_events) >= 1, "Expected at least 1 LOW_BATTERY_WARNING event"
    assert final_soc <= 15.0


def test_adas_events_scenario():
    # Test trip with specified adas_count
    readings, events, _, _ = generate_trip(
        rng=random.Random(42),
        start_time=datetime(2026, 10, 21, 18, 0),
        duration_min=45,
        mode="highway",
        soc=80.0,
        odometer=12500.0,
        ambient=20.0,
        eff_factor=1.0,
        adas_count=2,
    )

    adas_events = [e for e in events if e[2] == "ADAS_DISENGAGEMENT"]
    assert len(adas_events) == 2, f"Expected exactly 2 ADAS events, got {len(adas_events)}"


def test_cold_weather_efficiency_change():
    # Warm trip
    readings_warm, _, _, _ = generate_trip(
        rng=random.Random(100),
        start_time=datetime(2026, 10, 5, 8, 0),
        duration_min=40,
        mode="highway",
        soc=90.0,
        odometer=10000.0,
        ambient=26.0,
        eff_factor=1.0,
    )
    # Cold trip with 25% higher consumption factor
    readings_cold, _, _, _ = generate_trip(
        rng=random.Random(100),
        start_time=datetime(2026, 10, 19, 8, 0),
        duration_min=40,
        mode="highway",
        soc=90.0,
        odometer=10500.0,
        ambient=10.0,
        eff_factor=1.25,
    )

    avg_wh_warm = sum(r[5] for r in readings_warm) / len(readings_warm)
    avg_wh_cold = sum(r[5] for r in readings_cold) / len(readings_cold)

    assert avg_wh_cold > avg_wh_warm * 1.15, (
        f"Expected cold consumption ({avg_wh_cold:.1f} Wh/km) to be noticeably higher "
        f"than warm consumption ({avg_wh_warm:.1f} Wh/km)"
    )


def test_generate_history_integrity():
    # Generate 3 days of history
    readings, events = generate_history(days=3, seed=123)

    assert len(readings) > 0, "No readings generated"
    assert len(events) > 0, "No events generated"

    # Check for no duplicate timestamps
    timestamps = [r[1] for r in readings]
    assert len(timestamps) == len(set(timestamps)), "Found duplicate timestamps in generated history!"
