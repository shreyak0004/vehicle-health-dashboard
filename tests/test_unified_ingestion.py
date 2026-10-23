"""Unit tests for Priority 2: Unified Vehicle Data Ingestion.

Verifies:
1. Small, common data format (UnifiedVehicleRecord) with timestamp, vehicle_id, signal_name, value, unit, source, metadata.
2. Parsing sample CSV files into the common format with source labelled as 'recorded' or 'simulated'.
3. Support for both wide and long CSV representations.
4. Persistence into existing SQLite tables without schema migration.
"""
import io
import sqlite3
from pathlib import Path
import pytest

from ingestion.normalizer import (
    UnifiedVehicleRecord,
    create_unified_record,
    records_to_sqlite_tuples,
)
from ingestion.csv_importer import (
    parse_csv_to_records,
    import_csv_to_db,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_unified_record_creation():
    rec = create_unified_record(
        timestamp="2026-10-23 10:00:00",
        vehicle_id="EV-001",
        signal_name="speed",
        value=85.5,
        unit="km/h",
        source="recorded",
        metadata={"trip_id": "trip-01"},
    )
    assert isinstance(rec, UnifiedVehicleRecord)
    assert rec.timestamp == "2026-10-23 10:00:00"
    assert rec.vehicle_id == "EV-001"
    assert rec.signal_name == "speed"
    assert rec.value == 85.5
    assert rec.unit == "km/h"
    assert rec.source == "recorded"
    assert rec.metadata["trip_id"] == "trip-01"


def test_parse_sample_recorded_csv():
    csv_path = PROJECT_ROOT / "data" / "sample_recorded_trip.csv"
    assert csv_path.exists(), "Sample recorded CSV file must exist"

    records = parse_csv_to_records(csv_path, default_source="recorded")
    assert len(records) > 0

    # Verify all records have source labelled as 'recorded'
    assert all(r.source == "recorded" for r in records)

    # Check signal diversity
    signals = {r.signal_name for r in records}
    assert "speed" in signals
    assert "battery_temp" in signals
    assert "battery_soc" in signals
    assert "energy_wh_per_km" in signals

    # Verify scenario metadata preservation
    assert all(r.metadata.get("scenario") in ["commute", "highway_stretch"] for r in records)


def test_parse_sample_simulated_csv():
    csv_path = PROJECT_ROOT / "data" / "sample_simulated_trip.csv"
    assert csv_path.exists(), "Sample simulated CSV file must exist"

    records = parse_csv_to_records(csv_path, default_source="simulated")
    assert len(records) > 0

    # Verify all records have source labelled as 'simulated'
    assert all(r.source == "simulated" for r in records)

    signals = {r.signal_name for r in records}
    assert "speed" in signals
    assert "energy_wh_per_km" in signals
    assert "ambient_temp" in signals
    assert "range_km" in signals

    # Verify scenario metadata
    assert all(r.metadata.get("scenario") == "cold_weather" for r in records)


def test_parse_csv_string_content():
    raw_csv = """timestamp,vehicle_id,speed,battery_soc,source
2026-10-23 11:00:00,EV-002,55.0,78.2,simulated
2026-10-23 11:01:00,EV-002,60.0,78.0,simulated
"""
    records = parse_csv_to_records(raw_csv)
    assert len(records) == 4  # 2 speed + 2 battery_soc
    assert all(r.vehicle_id == "EV-002" for r in records)
    assert all(r.source == "simulated" for r in records)


def test_sqlite_persistence_without_schema_migration(tmp_path):
    # Create SQLite DB using the exact existing production schema
    db_path = tmp_path / "test_import.db"
    conn = sqlite3.connect(db_path)
    schema_path = PROJECT_ROOT / "database" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    csv_path = PROJECT_ROOT / "data" / "sample_recorded_trip.csv"
    r_count, e_count = import_csv_to_db(csv_path, conn, default_source="recorded")

    assert r_count == 5, f"Expected 5 readings from sample recorded CSV, got {r_count}"
    assert e_count == 0

    # Verify database contents
    cursor = conn.cursor()
    cursor.execute("SELECT speed, battery_temp, driving_mode, energy_wh_per_km FROM vehicle_readings ORDER BY timestamp")
    rows = cursor.fetchall()

    assert len(rows) == 5
    # First row: speed=42.5, battery_temp=28.2, driving_mode='city', energy_wh_per_km=138.0
    assert rows[0][0] == 42.5
    assert rows[0][1] == 28.2
    assert rows[0][2] == "city"
    assert rows[0][3] == 138.0

    # Fourth row: speed=98.5, driving_mode='highway'
    assert rows[3][0] == 98.5
    assert rows[3][2] == "highway"

    conn.close()
