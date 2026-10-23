"""Unit tests for Phase 3 multi-source vehicle ingestion adapters and pipeline."""
import sqlite3
import pytest

from ingestion.common_schema import SourceType, NormalizedTelemetry, NormalizedEvent
from ingestion.adapters.can_adapter import CanAdapter
from ingestion.adapters.someip_adapter import SomeIpAdapter
from ingestion.adapters.vhal_adapter import VhalAdapter
from ingestion.adapters.qnx_adapter import QnxAdapter
from ingestion.adapters.adas_adapter import AdasAdapter
from ingestion.adapters.camera_metadata_adapter import CameraMetadataAdapter
from ingestion.adapters.diagnostic_adapter import DiagnosticAdapter
from ingestion.pipeline import IngestionPipeline


def test_can_adapter_wheel_speed_and_bms():
    adapter = CanAdapter()
    
    # Wheel speed frame
    frame_speed = {
        "can_id": 0x101,
        "timestamp": "2026-10-22 14:00:00",
        "bus": "can0",
        "is_fd": False,
        "signals": {"speed": 88.5, "odometer": 14200.0}
    }
    telemetry, event = adapter.parse_frame(frame_speed)
    assert telemetry is not None
    assert telemetry.speed == 88.5
    assert telemetry.odometer_km == 14200.0
    assert telemetry.source_type == SourceType.CAN
    assert event is None

    # CAN-FD BMS status frame with overheat trigger
    frame_bms = {
        "can_id": 0x202,
        "timestamp": "2026-10-22 14:01:00",
        "bus": "can_fd0",
        "is_fd": True,
        "signals": {"soc": 45.0, "battery_temp": 57.2, "ambient_temp": 24.0}
    }
    telemetry, event = adapter.parse_frame(frame_bms)
    assert telemetry is not None
    assert telemetry.battery_temp == 57.2
    assert telemetry.battery_soc == 45.0
    assert telemetry.source_type == SourceType.CAN_FD
    assert event is not None
    assert event.event_type == "BATTERY_OVERHEAT_WARNING"
    assert event.severity == "critical"


def test_someip_adapter():
    adapter = SomeIpAdapter()

    # PowertrainService notification
    packet = {
        "service_id": 0x1000,
        "method_id": 0x8001,
        "client_id": 0x01,
        "session_id": 0x10,
        "timestamp": "2026-10-22 14:05:00",
        "payload": {
            "speed_kmh": 65.0,
            "battery_soc_pct": 82.5,
            "estimated_range_km": 280.0,
            "drive_mode": "highway"
        }
    }
    telemetry, event = adapter.parse_packet(packet)
    assert telemetry is not None
    assert telemetry.speed == 65.0
    assert telemetry.battery_soc == 82.5
    assert telemetry.driving_mode == "highway"
    assert telemetry.source_type == SourceType.SOME_IP
    assert event is None


def test_vhal_adapter():
    adapter = VhalAdapter()

    # Android VHAL vehicle speed (reported in m/s: 25 m/s = 90 km/h)
    prop_speed = {
        "prop_id": VhalAdapter.PROP_PERF_VEHICLE_SPEED,
        "timestamp_ns": 1729600000000000000,
        "value": 25.0
    }
    telemetry, _ = adapter.parse_property(prop_speed)
    assert telemetry is not None
    assert round(telemetry.speed, 1) == 90.0
    assert telemetry.source_type == SourceType.ANDROID_VHAL

    # Android VHAL battery SOC
    prop_soc = {
        "prop_id": VhalAdapter.PROP_EV_BATTERY_LEVEL,
        "timestamp_ns": 1729600000000000000,
        "value": 14.2
    }
    telemetry, _ = adapter.parse_property(prop_soc)
    assert telemetry is not None
    assert telemetry.battery_soc == 14.2


def test_qnx_adapter():
    adapter = QnxAdapter()
    log_line = "2026-10-13 18:54:00 [CRIT] bms_guard: High temperature warning triggered at 56.4 C"
    event = adapter.parse_log_line(log_line)

    assert event is not None
    assert event.source_type == SourceType.QNX_LOG
    assert event.severity == "critical"
    assert event.event_type == "BATTERY_OVERHEAT_WARNING"
    assert "[bms_guard]" in event.description


def test_adas_adapter():
    adapter = AdasAdapter()
    event_data = {
        "timestamp": "2026-10-21 18:44:00",
        "type": "ADAS_DISENGAGEMENT",
        "reason": "Driver took over steering",
        "speed_kmh": 95.0,
        "severity": "warning"
    }
    event = adapter.parse_event(event_data)
    assert event is not None
    assert event.source_type == SourceType.ADAS
    assert event.event_type == "ADAS_DISENGAGEMENT"
    assert event.description == "Driver took over steering"
    assert event.metadata["speed_kmh"] == 95.0


def test_camera_metadata_adapter():
    adapter = CameraMetadataAdapter()

    # Lens obstruction triggers ADAS disengagement
    event = adapter.parse_metadata({
        "timestamp": "2026-10-21 18:18:00",
        "camera_id": "front_narrow",
        "lens_obstructed": True,
        "lane_confidence": 0.10
    })
    assert event is not None
    assert event.source_type == SourceType.CAMERA_METADATA
    assert event.event_type == "ADAS_DISENGAGEMENT"
    assert "Camera view obstructed" in event.description


def test_diagnostic_adapter_dtc():
    adapter = DiagnosticAdapter()

    # DTC P0A7E (Battery Over-Temperature)
    event = adapter.parse_dtc({
        "dtc_code": "P0A7E",
        "status": "confirmed",
        "timestamp": "2026-10-13 18:54:00",
        "ecu": "BMS_Master"
    })
    assert event is not None
    assert event.source_type == SourceType.DIAGNOSTIC_LOG
    assert event.event_type == "BATTERY_OVERHEAT_WARNING"
    assert event.severity == "critical"
    assert "P0A7E" in event.description


def test_ingestion_pipeline_persistence_in_memory():
    pipeline = IngestionPipeline()
    
    # Create test SQLite schema
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE vehicle_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            speed REAL,
            battery_temp REAL,
            battery_soc REAL,
            energy_wh_per_km REAL,
            driving_mode TEXT,
            odometer_km REAL,
            ambient_temp REAL,
            range_km REAL
        );
        CREATE TABLE vehicle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT,
            description TEXT
        );
    """)

    # 1. Ingest CAN reading
    t_can, e_can = pipeline.ingest_can_frame({
        "can_id": 0x101,
        "timestamp": "2026-10-22 15:00:00",
        "signals": {"speed": 72.0, "odometer": 15000.0}
    })
    
    # 2. Ingest QNX Event
    e_qnx = pipeline.ingest_qnx_log("2026-10-22 15:00:00 [CRIT] bms: Battery pack temperature 57.0 C")

    # 3. Ingest Diagnostic DTC
    e_dtc = pipeline.ingest_diagnostic_code({
        "dtc_code": "P0A7E",
        "timestamp": "2026-10-22 15:00:00"
    })

    t_count, e_count = pipeline.persist(
        conn,
        telemetries=[t_can] if t_can else [],
        events=[e for e in [e_can, e_qnx, e_dtc] if e]
    )

    assert t_count == 1
    assert e_count == 2  # QNX + DTC

    # Verify query
    cursor = conn.cursor()
    cursor.execute("SELECT speed, odometer_km FROM vehicle_readings")
    row = cursor.fetchone()
    assert row[0] == 72.0
    assert row[1] == 15000.0

    cursor.execute("SELECT COUNT(*) FROM vehicle_events WHERE event_type = 'BATTERY_OVERHEAT_WARNING'")
    count = cursor.fetchone()[0]
    assert count == 2
    conn.close()
