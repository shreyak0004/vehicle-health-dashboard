"""Diagnostic Trouble Code (DTC) and UDS Diagnostic Log Adapter.

Parses standardized automotive diagnostic records, freeze-frame snapshots, and OBD-II/UDS event logs.
"""
from typing import Dict, Any, Optional
from ingestion.common_schema import NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class DiagnosticAdapter:
    """Ingests OBD-II / ISO 14229 UDS DTC events with snapshot freeze-frame data."""

    KNOWN_DTCS = {
        "P0A7E": ("BATTERY_OVERHEAT_WARNING", "critical", "Hybrid/EV Battery Pack Over-Temperature"),
        "P0A80": ("BATTERY_DEGRADATION_ALERT", "warning", "Replace Hybrid Battery Pack - Capacity Imbalance"),
        "P0562": ("LOW_BATTERY_WARNING", "warning", "System Voltage Low (BMS threshold triggered)"),
        "C1001": ("ADAS_DISENGAGEMENT", "warning", "Forward Looking Camera System Malfunction"),
        "U0100": ("ECU_COMMS_LOST", "critical", "Lost Communication with ECM/Powertrain Control Module"),
    }

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_dtc(self, dtc_record: Dict[str, Any]) -> Optional[NormalizedEvent]:
        """Parses a diagnostic DTC record.

        Structure:
        {
            "dtc_code": "P0A7E",
            "status": "confirmed",             # 'confirmed', 'pending', 'historical'
            "timestamp": "2026-10-13 18:54:00",
            "ecu": "BMS_Master",
            "freeze_frame": {"battery_temp": 56.5, "speed": 98.0}
        }
        """
        code = dtc_record.get("dtc_code", "").upper().strip()
        ts = normalize_timestamp(dtc_record.get("timestamp"))
        status = dtc_record.get("status", "confirmed").lower()
        vehicle_id = dtc_record.get("vehicle_id", self.default_vehicle_id)

        lookup = self.KNOWN_DTCS.get(code)
        if lookup:
            event_type, severity, default_desc = lookup
        else:
            event_type = f"DTC_{code}"
            severity = "warning" if status == "pending" else "critical"
            default_desc = f"Diagnostic Trouble Code {code} reported by {dtc_record.get('ecu', 'ECU')}"

        meta = {
            "dtc": code,
            "status": status,
            "ecu": dtc_record.get("ecu"),
            "freeze_frame": dtc_record.get("freeze_frame", {}),
        }

        return NormalizedEvent(
            vehicle_id=vehicle_id,
            timestamp=ts,
            source_type=SourceType.DIAGNOSTIC_LOG,
            event_type=event_type,
            severity=severity,
            description=f"[{code}] {default_desc}",
            metadata=meta,
        )
