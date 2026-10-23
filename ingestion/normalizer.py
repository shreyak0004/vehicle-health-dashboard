"""Validation and normalization utilities for unified vehicle ingestion."""
from datetime import datetime
from typing import Any, Tuple, Optional
from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent

FMT = "%Y-%m-%d %H:%M:%S"


def normalize_timestamp(raw_ts: Any) -> str:
    """Converts diverse timestamp formats (ISO strings, Unix epochs, datetime) to standard YYYY-MM-DD HH:MM:SS."""
    if isinstance(raw_ts, datetime):
        return raw_ts.strftime(FMT)
    
    if isinstance(raw_ts, (int, float)):
        # If timestamp is in nanoseconds (e.g. Android nanoseconds > 1e14)
        if raw_ts > 1e14:
            raw_ts = raw_ts / 1e9
        # If timestamp is in milliseconds (e.g. JS / Android millis > 1e11)
        elif raw_ts > 1e11:
            raw_ts = raw_ts / 1000.0
        try:
            return datetime.fromtimestamp(raw_ts).strftime(FMT)
        except (OSError, OverflowError, ValueError):
            return datetime.now().strftime(FMT)

    if isinstance(raw_ts, str):
        # Strip trailing Z or ISO-8601 formatting
        clean_ts = raw_ts.replace("T", " ").replace("Z", "")
        # Truncate fractional seconds if present
        if "." in clean_ts:
            clean_ts = clean_ts.split(".")[0]
        try:
            dt = datetime.strptime(clean_ts, FMT)
            return dt.strftime(FMT)
        except ValueError:
            pass
        # Fallback to date only
        try:
            dt = datetime.strptime(clean_ts, "%Y-%m-%d")
            return dt.strftime(FMT)
        except ValueError:
            pass

    return datetime.now().strftime(FMT)


def validate_telemetry(t: NormalizedTelemetry) -> bool:
    """Ensures signal values conform to physical automotive bounds."""
    if not t.vehicle_id or not t.timestamp:
        return False
    
    if t.speed is not None and not (0.0 <= t.speed <= 260.0):
        return False
    
    if t.battery_soc is not None and not (0.0 <= t.battery_soc <= 100.0):
        return False

    if t.battery_temp is not None and not (-40.0 <= t.battery_temp <= 120.0):
        return False

    if t.ambient_temp is not None and not (-50.0 <= t.ambient_temp <= 70.0):
        return False

    if t.odometer_km is not None and t.odometer_km < 0:
        return False

    return True


def validate_event(e: NormalizedEvent) -> bool:
    """Validates discrete event severity and fields."""
    if not e.vehicle_id or not e.timestamp or not e.event_type:
        return False
    
    valid_severities = {"info", "warning", "critical"}
    if e.severity.lower() not in valid_severities:
        return False

    return True


def to_db_reading_tuple(t: NormalizedTelemetry) -> Tuple:
    """Converts NormalizedTelemetry to the exact column structure expected by vehicle_readings."""
    return (
        t.vehicle_id,
        t.timestamp,
        round(t.speed, 1) if t.speed is not None else None,
        round(t.battery_temp, 1) if t.battery_temp is not None else None,
        round(t.battery_soc, 2) if t.battery_soc is not None else None,
        round(t.energy_wh_per_km, 1) if t.energy_wh_per_km is not None else None,
        t.driving_mode or "city",
        round(t.odometer_km, 1) if t.odometer_km is not None else 0.0,
        round(t.ambient_temp, 1) if t.ambient_temp is not None else 25.0,
        round(t.range_km, 1) if t.range_km is not None else 0.0,
    )


def to_db_event_tuple(e: NormalizedEvent) -> Tuple:
    """Converts NormalizedEvent to the column structure expected by vehicle_events."""
    return (
        e.vehicle_id,
        e.timestamp,
        e.event_type,
        e.severity.lower(),
        e.description,
    )


# =====================================================================
# Small, Common Unified Vehicle Data Format (Priority 2)
# Accepts synthetic and recorded data now and supports real adapters later.
# =====================================================================
from dataclasses import dataclass, field
from typing import Dict, List
from collections import defaultdict


STANDARD_UNITS = {
    "speed": "km/h",
    "battery_temp": "°C",
    "battery_soc": "%",
    "energy_wh_per_km": "Wh/km",
    "driving_mode": "",
    "odometer_km": "km",
    "ambient_temp": "°C",
    "range_km": "km",
}

SIGNAL_ALIASES = {
    "speed": "speed",
    "vehicle_speed": "speed",
    "speed_kmh": "speed",
    "battery_temp": "battery_temp",
    "battery_temperature": "battery_temp",
    "temp_battery": "battery_temp",
    "soc": "battery_soc",
    "battery_soc": "battery_soc",
    "state_of_charge": "battery_soc",
    "energy_wh_per_km": "energy_wh_per_km",
    "consumption": "energy_wh_per_km",
    "energy_consumption": "energy_wh_per_km",
    "wh_per_km": "energy_wh_per_km",
    "driving_mode": "driving_mode",
    "mode": "driving_mode",
    "drive_mode": "driving_mode",
    "odometer": "odometer_km",
    "odometer_km": "odometer_km",
    "odo": "odometer_km",
    "ambient_temp": "ambient_temp",
    "outside_temp": "ambient_temp",
    "ambient_temperature": "ambient_temp",
    "range": "range_km",
    "range_km": "range_km",
    "estimated_range": "range_km",
}


@dataclass
class UnifiedVehicleRecord:
    """One small, common data format for vehicle telemetry and events.

    Accepts synthetic and recorded data now and supports real adapters later.

    Fields:
    - timestamp: Normalized timestamp string (YYYY-MM-DD HH:MM:SS)
    - vehicle_id: Unique vehicle identifier (e.g. 'EV-001')
    - signal_name: Standardized signal or event name (e.g. 'speed', 'battery_temp')
    - value: Numerical, boolean, or string value
    - unit: Engineering measurement unit (e.g. 'km/h', '°C', '%', 'Wh/km', 'km')
    - source: Data origin label ('recorded' or 'simulated')
    - metadata: Scenario or event metadata dictionary
    """
    timestamp: str
    vehicle_id: str
    signal_name: str
    value: Any
    unit: str = ""
    source: str = "simulated"     # 'recorded' | 'simulated'
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_signal_name(raw_name: str) -> str:
    """Standardizes heterogeneous signal names to common vehicle signals."""
    clean = raw_name.strip().lower().replace("-", "_").replace(" ", "_")
    return SIGNAL_ALIASES.get(clean, clean)


def create_unified_record(
    timestamp: Any,
    vehicle_id: str,
    signal_name: str,
    value: Any,
    unit: Optional[str] = None,
    source: str = "recorded",
    metadata: Optional[Dict[str, Any]] = None,
) -> UnifiedVehicleRecord:
    """Creates a normalized UnifiedVehicleRecord with validated timestamp, signal name, and unit."""
    ts_norm = normalize_timestamp(timestamp)
    sig_norm = normalize_signal_name(signal_name)
    u = unit if unit is not None else STANDARD_UNITS.get(sig_norm, "")
    src = "recorded" if str(source).lower().startswith("rec") else "simulated"
    return UnifiedVehicleRecord(
        timestamp=ts_norm,
        vehicle_id=vehicle_id,
        signal_name=sig_norm,
        value=value,
        unit=u,
        source=src,
        metadata=metadata or {},
    )


def records_to_sqlite_tuples(records: List[UnifiedVehicleRecord]) -> Tuple[List[tuple], List[tuple]]:
    """Pivots UnifiedVehicleRecord list into existing SQLite vehicle_readings and vehicle_events tuples.

    Keeps the existing SQLite tables working with zero schema migration.
    """
    readings_by_time = defaultdict(dict)
    event_tuples = []

    for r in records:
        if r.signal_name in STANDARD_UNITS or r.signal_name in SIGNAL_ALIASES.values():
            try:
                val = float(r.value) if r.signal_name != "driving_mode" else str(r.value)
            except (ValueError, TypeError):
                val = r.value
            readings_by_time[(r.vehicle_id, r.timestamp)][r.signal_name] = val
        elif r.signal_name.endswith("_WARNING") or r.signal_name.endswith("_EVENT") or "event" in r.metadata:
            # Discrete event record
            severity = r.metadata.get("severity", "info")
            desc = str(r.value) if r.value else r.metadata.get("description", r.signal_name)
            event_tuples.append((
                r.vehicle_id,
                r.timestamp,
                r.signal_name,
                severity,
                desc,
            ))

    reading_tuples = []
    for (veh_id, ts), sigs in sorted(readings_by_time.items(), key=lambda x: x[0][1]):
        reading_tuples.append((
            veh_id,
            ts,
            round(float(sigs.get("speed")), 1) if sigs.get("speed") is not None else None,
            round(float(sigs.get("battery_temp")), 1) if sigs.get("battery_temp") is not None else None,
            round(float(sigs.get("battery_soc")), 2) if sigs.get("battery_soc") is not None else None,
            round(float(sigs.get("energy_wh_per_km")), 1) if sigs.get("energy_wh_per_km") is not None else None,
            str(sigs.get("driving_mode") or "city"),
            round(float(sigs.get("odometer_km")), 1) if sigs.get("odometer_km") is not None else 0.0,
            round(float(sigs.get("ambient_temp")), 1) if sigs.get("ambient_temp") is not None else 25.0,
            round(float(sigs.get("range_km")), 1) if sigs.get("range_km") is not None else 0.0,
        ))

    return reading_tuples, event_tuples
