"""Multi-Source Vehicle Ingestion Pipeline.

Orchestrates decoding, validation, normalization, and database persistence across all automotive adapters.
"""
from typing import List, Dict, Any, Tuple, Optional
import sqlite3

from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent, SourceType
from ingestion.normalizer import (
    validate_telemetry,
    validate_event,
    to_db_reading_tuple,
    to_db_event_tuple,
)
from ingestion.adapters.can_adapter import CanAdapter
from ingestion.adapters.someip_adapter import SomeIpAdapter
from ingestion.adapters.vhal_adapter import VhalAdapter
from ingestion.adapters.qnx_adapter import QnxAdapter
from ingestion.adapters.adas_adapter import AdasAdapter
from ingestion.adapters.camera_metadata_adapter import CameraMetadataAdapter
from ingestion.adapters.diagnostic_adapter import DiagnosticAdapter

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


class IngestionPipeline:
    """Unified ingestion pipeline coordinating all source adapters with rigorous bounds validation."""

    def __init__(self, vehicle_id: str = "EV-001"):
        self.vehicle_id = vehicle_id
        self.can_adapter = CanAdapter(vehicle_id)
        self.someip_adapter = SomeIpAdapter(vehicle_id)
        self.vhal_adapter = VhalAdapter(vehicle_id)
        self.qnx_adapter = QnxAdapter(vehicle_id)
        self.adas_adapter = AdasAdapter(vehicle_id)
        self.camera_adapter = CameraMetadataAdapter(vehicle_id)
        self.diagnostic_adapter = DiagnosticAdapter(vehicle_id)

    def ingest_can_frame(self, frame: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        telemetry, event = self.can_adapter.parse_frame(frame)
        return self._filter_valid(telemetry, event)

    def ingest_someip_packet(self, packet: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        telemetry, event = self.someip_adapter.parse_packet(packet)
        return self._filter_valid(telemetry, event)

    def ingest_vhal_property(self, prop: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        telemetry, event = self.vhal_adapter.parse_property(prop)
        return self._filter_valid(telemetry, event)

    def ingest_qnx_log(self, line: str) -> Optional[NormalizedEvent]:
        event = self.qnx_adapter.parse_log_line(line, self.vehicle_id)
        if event and validate_event(event):
            return event
        return None

    def ingest_adas_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedEvent]:
        event = self.adas_adapter.parse_event(event_data)
        if event and validate_event(event):
            return event
        return None

    def ingest_camera_metadata(self, meta_data: Dict[str, Any]) -> Optional[NormalizedEvent]:
        event = self.camera_adapter.parse_metadata(meta_data)
        if event and validate_event(event):
            return event
        return None

    def ingest_diagnostic_code(self, dtc_data: Dict[str, Any]) -> Optional[NormalizedEvent]:
        event = self.diagnostic_adapter.parse_dtc(dtc_data)
        if event and validate_event(event):
            return event
        return None

    def _filter_valid(
        self, telemetry: Optional[NormalizedTelemetry], event: Optional[NormalizedEvent]
    ) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        valid_telemetry = telemetry if (telemetry and validate_telemetry(telemetry)) else None
        valid_event = event if (event and validate_event(event)) else None
        return valid_telemetry, valid_event

    def persist(
        self,
        conn: sqlite3.Connection,
        telemetries: Optional[List[NormalizedTelemetry]] = None,
        events: Optional[List[NormalizedEvent]] = None,
    ) -> Tuple[int, int]:
        """Saves validated records into the SQLite database."""
        t_count, e_count = 0, 0
        if telemetries:
            valid_t = [to_db_reading_tuple(t) for t in telemetries if validate_telemetry(t)]
            if valid_t:
                conn.executemany(INSERT_READING_SQL, valid_t)
                t_count = len(valid_t)

        if events:
            valid_e = [to_db_event_tuple(e) for e in events if validate_event(e)]
            if valid_e:
                conn.executemany(INSERT_EVENT_SQL, valid_e)
                e_count = len(valid_e)

        conn.commit()
        return t_count, e_count
