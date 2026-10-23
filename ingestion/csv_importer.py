"""Unified CSV Importer for Vehicle Telemetry and Events.

Parses recorded and simulated CSV data into the common UnifiedVehicleRecord format
and persists records into existing SQLite tables with zero schema migration.
"""
import csv
import io
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict, Any

from ingestion.normalizer import (
    UnifiedVehicleRecord,
    create_unified_record,
    records_to_sqlite_tuples,
    STANDARD_UNITS,
    SIGNAL_ALIASES,
)


INSERT_READING_SQL = """
INSERT INTO vehicle_readings
(vehicle_id, timestamp, speed, battery_temp, battery_soc, energy_wh_per_km,
 driving_mode, odometer_km, ambient_temp, range_km)
VALUES (?,?,?,?,?,?,?,?,?,?)
"""

INSERT_EVENT_SQL = """
INSERT INTO vehicle_events
(vehicle_id, timestamp, event_type, severity, description)
VALUES (?,?,?,?,?)
"""


def parse_csv_to_records(
    csv_source: Union[str, Path, io.StringIO],
    default_source: str = "recorded",
    default_vehicle_id: str = "EV-001",
    scenario_metadata: Optional[Dict[str, Any]] = None,
) -> List[UnifiedVehicleRecord]:
    """Parses a CSV file or string into a list of normalized UnifiedVehicleRecord objects.

    Supports both:
    1. Wide-format CSV: columns like 'timestamp', 'speed', 'battery_temp', 'soc', etc.
    2. Long-format CSV: columns 'timestamp', 'signal_name', 'value', 'unit', etc.

    Each record is normalized and labelled with its source ('recorded' or 'simulated').
    """
    records: List[UnifiedVehicleRecord] = []

    # Handle file path vs raw CSV text
    if isinstance(csv_source, Path) or (isinstance(csv_source, str) and "\n" not in csv_source and Path(csv_source).exists()):
        with open(csv_source, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    elif isinstance(csv_source, io.StringIO):
        reader = csv.DictReader(csv_source)
        rows = list(reader)
    else:
        # String content
        reader = csv.DictReader(io.StringIO(str(csv_source)))
        rows = list(reader)

    if not rows:
        return records

    fieldnames = [fn.strip().lower() for fn in (reader.fieldnames or [])]
    is_long_format = "signal_name" in fieldnames and "value" in fieldnames

    for row in rows:
        # Clean row keys
        clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v is not None}
        ts = clean_row.get("timestamp") or clean_row.get("time") or clean_row.get("datetime")
        if not ts:
            continue

        veh_id = clean_row.get("vehicle_id") or clean_row.get("vin") or default_vehicle_id
        source = clean_row.get("source") or default_source

        # Extract extra metadata
        row_metadata = dict(scenario_metadata or {})
        for extra_key in ["scenario", "event", "trip_id", "severity", "notes"]:
            if extra_key in clean_row:
                row_metadata[extra_key] = clean_row[extra_key]

        if is_long_format:
            sig_name = clean_row.get("signal_name", "")
            raw_val = clean_row.get("value", "")
            unit = clean_row.get("unit") or STANDARD_UNITS.get(sig_name, "")
            rec = create_unified_record(
                timestamp=ts,
                vehicle_id=veh_id,
                signal_name=sig_name,
                value=raw_val,
                unit=unit,
                source=source,
                metadata=row_metadata,
            )
            records.append(rec)
        else:
            # Wide format: pivot each known telemetry or event column into a UnifiedVehicleRecord
            for col_name, raw_val in clean_row.items():
                if col_name in ["timestamp", "time", "datetime", "vehicle_id", "vin", "source", "scenario", "trip_id", "severity"]:
                    continue
                if raw_val == "":
                    continue

                rec = create_unified_record(
                    timestamp=ts,
                    vehicle_id=veh_id,
                    signal_name=col_name,
                    value=raw_val,
                    source=source,
                    metadata=row_metadata,
                )
                records.append(rec)

    return records


def import_csv_to_db(
    csv_source: Union[str, Path, io.StringIO],
    conn: sqlite3.Connection,
    default_source: str = "recorded",
    default_vehicle_id: str = "EV-001",
    scenario_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[int, int]:
    """Parses CSV into UnifiedVehicleRecord and inserts into existing SQLite tables without schema migration.

    Returns (readings_inserted_count, events_inserted_count).
    """
    records = parse_csv_to_records(
        csv_source=csv_source,
        default_source=default_source,
        default_vehicle_id=default_vehicle_id,
        scenario_metadata=scenario_metadata,
    )

    if not records:
        return 0, 0

    readings, events = records_to_sqlite_tuples(records)

    cursor = conn.cursor()
    r_count = 0
    e_count = 0

    if readings:
        cursor.executemany(INSERT_READING_SQL, readings)
        r_count = len(readings)

    if events:
        cursor.executemany(INSERT_EVENT_SQL, events)
        e_count = len(events)

    conn.commit()
    return r_count, e_count
