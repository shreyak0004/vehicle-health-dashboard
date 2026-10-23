"""CAN and CAN-FD Message Adapter.

Parses recorded or simulated CAN/CAN-FD frames, applies DBC signal extraction,
and normalizes signals into the common telemetry schema with hardware provenance.
"""
from typing import Dict, Any, Tuple, Optional, List
from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class CanAdapter:
    """Decodes standard CAN (11/29-bit, 8 bytes) and CAN-FD (up to 64 bytes) frames."""

    ID_WHEEL_SPEED = 0x101
    ID_BMS_STATUS = 0x202
    ID_POWERTRAIN = 0x303

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_frame(self, frame: Dict[str, Any]) -> Tuple[Optional[NormalizedTelemetry], Optional[NormalizedEvent]]:
        """Parses a CAN or CAN-FD frame dictionary into normalized telemetry and optional event.

        Frame structure:
        {
            "can_id": 0x101,
            "timestamp": "2026-10-22 18:00:00" | float,
            "is_fd": True,
            "bus": "can0",
            "signals": { ... } OR "payload": bytes/hex
        }
        """
        can_id = frame.get("can_id")
        ts = normalize_timestamp(frame.get("timestamp"))
        is_fd = frame.get("is_fd", False)
        bus = frame.get("bus", "can0")
        signals = frame.get("signals", {})
        vehicle_id = frame.get("vehicle_id", self.default_vehicle_id)

        # Raw payload fallback extraction if signals dict wasn't pre-decoded
        payload = frame.get("payload")
        if not signals and payload:
            signals = self._decode_raw_payload(can_id, payload)

        telemetry: Optional[NormalizedTelemetry] = None
        event: Optional[NormalizedEvent] = None

        meta = {
            "can_id": hex(can_id) if can_id is not None else None,
            "is_fd": is_fd,
            "bus": bus,
            "dlc": frame.get("dlc", 64 if is_fd else 8),
        }

        if can_id == self.ID_WHEEL_SPEED:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.CAN_FD if is_fd else SourceType.CAN,
                speed=signals.get("speed"),
                odometer_km=signals.get("odometer"),
                metadata=meta,
            )

        elif can_id == self.ID_BMS_STATUS:
            soc = signals.get("soc")
            temp = signals.get("battery_temp")
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.CAN_FD if is_fd else SourceType.CAN,
                battery_soc=soc,
                battery_temp=temp,
                ambient_temp=signals.get("ambient_temp"),
                metadata=meta,
            )

            # Planted CAN event generation on threshold violation
            if temp is not None and temp >= 55.0:
                event = NormalizedEvent(
                    vehicle_id=vehicle_id,
                    timestamp=ts,
                    source_type=SourceType.CAN_FD if is_fd else SourceType.CAN,
                    event_type="BATTERY_OVERHEAT_WARNING",
                    severity="critical",
                    description=f"CAN BMS alert: Pack temperature {temp:.1f} °C exceeds safe limits",
                    metadata=meta,
                )
            elif soc is not None and soc <= 15.0:
                event = NormalizedEvent(
                    vehicle_id=vehicle_id,
                    timestamp=ts,
                    source_type=SourceType.CAN_FD if is_fd else SourceType.CAN,
                    event_type="LOW_BATTERY_WARNING",
                    severity="warning",
                    description=f"CAN BMS alert: Low battery state of charge ({soc:.1f}%)",
                    metadata=meta,
                )

        elif can_id == self.ID_POWERTRAIN:
            telemetry = NormalizedTelemetry(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.CAN_FD if is_fd else SourceType.CAN,
                energy_wh_per_km=signals.get("energy_wh_per_km"),
                driving_mode=signals.get("mode", "city"),
                range_km=signals.get("range_km"),
                metadata=meta,
            )

        return telemetry, event

    def _decode_raw_payload(self, can_id: int, payload: Any) -> Dict[str, Any]:
        """Simple DBC unpacker for simulated byte payloads."""
        if isinstance(payload, str):
            payload = bytes.fromhex(payload.replace("0x", ""))
        signals = {}
        if can_id == self.ID_WHEEL_SPEED and len(payload) >= 2:
            # 2 bytes speed (0.1 resolution)
            signals["speed"] = (payload[0] << 8 | payload[1]) * 0.1
        elif can_id == self.ID_BMS_STATUS and len(payload) >= 4:
            signals["soc"] = payload[0] * 0.5
            signals["battery_temp"] = payload[1] - 40.0
        return signals
