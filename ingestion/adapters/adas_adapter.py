"""ADAS (Advanced Driver Assistance Systems) Event Adapter.

Ingests ADAS events including lane-keeping disengagements, forward collision warnings,
and driver takeover events with safety metadata.
"""
from typing import Dict, Any, Optional
from ingestion.common_schema import NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class AdasAdapter:
    """Ingests ADAS domain controller alerts and disengagement notifications."""

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedEvent]:
        """Parses an ADAS event payload.

        Structure:
        {
            "timestamp": "2026-10-21 18:44:00",
            "type": "ADAS_DISENGAGEMENT",
            "reason": "Lane markings not detected",
            "speed_kmh": 92.5,
            "subsystem": "FrontCamera_Mobileye",
            "severity": "warning"
        }
        """
        raw_ts = event_data.get("timestamp")
        ts = normalize_timestamp(raw_ts)
        event_type = event_data.get("type", "ADAS_DISENGAGEMENT")
        reason = event_data.get("reason", "Driver took over manual control")
        severity = event_data.get("severity", "warning").lower()
        vehicle_id = event_data.get("vehicle_id", self.default_vehicle_id)

        meta = {
            "subsystem": event_data.get("subsystem", "ADAS_Core"),
            "speed_kmh": event_data.get("speed_kmh"),
            "confidence": event_data.get("confidence", 1.0),
        }

        return NormalizedEvent(
            vehicle_id=vehicle_id,
            timestamp=ts,
            source_type=SourceType.ADAS,
            event_type=event_type,
            severity=severity,
            description=reason,
            metadata=meta,
        )
