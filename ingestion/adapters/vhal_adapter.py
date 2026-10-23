"""Android Automotive OS Vehicle HAL (VHAL) Adapter.

Maps Android VehiclePropValue property updates (AOSP VehicleProperty IDs) into unified vehicle telemetry.
"""
from typing import Dict, Any, Tuple, Optional
from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class VhalAdapter:
    """Ingests VehiclePropValue dictionaries according to Android Automotive OS VHAL specifications."""

    # Standard AOSP Vehicle Property IDs
    PROP_PERF_VEHICLE_SPEED = 0x11600207           # float (m/s)
    PROP_EV_BATTERY_LEVEL = 0x11600501             # float (% or Wh)
    PROP_ENV_OUTSIDE_TEMPERATURE = 0x11600302      # float (Celsius)
    PROP_EV_BATTERY_TEMPERATURE = 0x11600502       # float (Celsius)
    PROP_PERF_ODOMETER = 0x11600204                # float (km)

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_property(self, prop: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        """Parses an Android VHAL property update.

        Structure:
        {
            "prop_id": 0x11600207,
            "area_id": 0,
            "timestamp_ns": 1729600000000000000,
            "value": 25.0,                         # e.g. 25 m/s = 90 km/h
            "status": 0
        }
        """
        prop_id = prop.get("prop_id")
        raw_ts = prop.get("timestamp_ns") or prop.get("timestamp")
        ts = normalize_timestamp(raw_ts)
        val = prop.get("value")
        vehicle_id = prop.get("vehicle_id", self.default_vehicle_id)

        meta = {
            "prop_id": hex(prop_id) if prop_id is not None else None,
            "area_id": prop.get("area_id", 0),
            "status": prop.get("status", 0),
        }

        telemetry: Optional[NormalizedTelemetry] = None
        event: Optional[NormalizedEvent] = None

        if prop_id == self.PROP_PERF_VEHICLE_SPEED and val is not None:
            # Android VHAL reports vehicle speed in m/s; convert to km/h
            speed_kmh = float(val) * 3.6
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.ANDROID_VHAL,
                speed=speed_kmh,
                metadata=meta,
            )

        elif prop_id == self.PROP_EV_BATTERY_LEVEL and val is not None:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.ANDROID_VHAL,
                battery_soc=float(val),
                metadata=meta,
            )

        elif prop_id == self.PROP_EV_BATTERY_TEMPERATURE and val is not None:
            temp = float(val)
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.ANDROID_VHAL,
                battery_temp=temp,
                metadata=meta,
            )
            if temp >= 55.0:
                event = NormalizedEvent(
                    vehicle_id=vehicle_id,
                    timestamp=ts,
                    source_type=SourceType.ANDROID_VHAL,
                    event_type="BATTERY_OVERHEAT_WARNING",
                    severity="critical",
                    description=f"Android VHAL Battery Sensor critical threshold reached ({temp:.1f} °C)",
                    metadata=meta,
                )

        elif prop_id == self.PROP_ENV_OUTSIDE_TEMPERATURE and val is not None:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.ANDROID_VHAL,
                ambient_temp=float(val),
                metadata=meta,
            )

        elif prop_id == self.PROP_PERF_ODOMETER and val is not None:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.ANDROID_VHAL,
                odometer_km=float(val),
                metadata=meta,
            )

        return telemetry, event
