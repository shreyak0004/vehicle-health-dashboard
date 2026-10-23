"""SOME/IP (Scalable service-Oriented MiddlewarE over IP) Protocol Adapter.

Ingests Service-Oriented Architecture (SOA) packets from modern SDV Ethernet networks.
"""
from typing import Dict, Any, Tuple, Optional
from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class SomeIpAdapter:
    """Decodes SOME/IP header, service method/event IDs, and payload serialized data."""

    SERVICE_POWERTRAIN = 0x1000
    SERVICE_THERMAL = 0x2000

    METHOD_POWERTRAIN_NOTIFY = 0x8001
    METHOD_THERMAL_STATUS = 0x8002

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_packet(self, packet: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        """Parses a SOME/IP service packet.

        Structure:
        {
            "service_id": 0x1000,
            "method_id": 0x8001,
            "client_id": 0x0001,
            "session_id": 0x002A,
            "timestamp": "...",
            "payload": { ... }
        }
        """
        service_id = packet.get("service_id")
        method_id = packet.get("method_id")
        ts = normalize_timestamp(packet.get("timestamp"))
        payload = packet.get("payload", {})
        vehicle_id = packet.get("vehicle_id", self.default_vehicle_id)

        meta = {
            "service_id": hex(service_id) if service_id else None,
            "method_id": hex(method_id) if method_id else None,
            "client_id": packet.get("client_id"),
            "session_id": packet.get("session_id"),
            "interface_version": packet.get("interface_version", 1),
        }

        telemetry: Optional[NormalizedTelemetry] = None
        event: Optional[NormalizedEvent] = None

        if service_id == self.SERVICE_POWERTRAIN:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.SOME_IP,
                speed=payload.get("speed_kmh"),
                battery_soc=payload.get("battery_soc_pct"),
                range_km=payload.get("estimated_range_km"),
                odometer_km=payload.get("odometer_km"),
                driving_mode=payload.get("drive_mode", "city"),
                metadata=meta,
            )

        elif service_id == self.SERVICE_THERMAL:
            temp = payload.get("battery_temp_c")
            ambient = payload.get("ambient_temp_c")
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.SOME_IP,
                battery_temp=temp,
                ambient_temp=ambient,
                metadata=meta,
            )

            if temp is not None and temp >= 55.0:
                event = NormalizedEvent(
                    vehicle_id=vehicle_id,
                    timestamp=ts,
                    source_type=SourceType.SOME_IP,
                    event_type="BATTERY_OVERHEAT_WARNING",
                    severity="critical",
                    description=f"SOME/IP ThermalService alert: Battery core temperature {temp:.1f} °C",
                    metadata=meta,
                )

        return telemetry, event
