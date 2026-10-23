"""QNX Neutrino RTOS Log Adapter (slogger2 / syslog format).

Parses real-time system logs and diagnostic events from QNX safety controllers.
"""
import re
from typing import Dict, Any, Tuple, Optional
from ingestion.common_schema import NormalizedTelemetry, NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class QnxAdapter:
    """Parses QNX slogger2 lines and structured log payloads."""

    LOG_PATTERN = re.compile(
        r"^(?P<timestamp>[\d\-:\s]+)\s+\[(?P<severity>[A-Z]+)\]\s+(?P<process>[\w\-]+):\s+(?P<message>.+)$"
    )

    SEVERITY_MAP = {
        "CRIT": "critical",
        "EMERG": "critical",
        "ERR": "critical",
        "ERROR": "critical",
        "WARN": "warning",
        "WARNING": "warning",
        "INFO": "info",
        "NOTICE": "info",
    }

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_log_line(self, line: str, vehicle_id: Optional[str] = None) -> Optional[NormalizedEvent]:
        """Parses a raw QNX log string line.

        Example:
        '2026-10-13 18:54:00 [CRIT] thermal_guard: Battery cell temperature reached 56.4 C'
        """
        line = line.strip()
        match = self.LOG_PATTERN.match(line)
        if not match:
            return None

        data = match.groupdict()
        ts = normalize_timestamp(data["timestamp"])
        raw_sev = data["severity"].upper()
        severity = self.SEVERITY_MAP.get(raw_sev, "info")
        process = data["process"]
        message = data["message"]
        v_id = vehicle_id or self.default_vehicle_id

        # Categorize event type
        if "overheat" in message.lower() or "temperature" in message.lower() and severity == "critical":
            event_type = "BATTERY_OVERHEAT_WARNING"
        elif "adas" in process.lower() or "lane" in message.lower() or "steering" in message.lower():
            event_type = "ADAS_DISENGAGEMENT"
        elif "battery" in message.lower() and "low" in message.lower():
            event_type = "LOW_BATTERY_WARNING"
        else:
            event_type = f"QNX_{process.upper()}_ALERT"

        return NormalizedEvent(
            vehicle_id=v_id,
            timestamp=ts,
            source_type=SourceType.QNX_LOG,
            event_type=event_type,
            severity=severity,
            description=f"[{process}] {message}",
            metadata={"process": process, "raw_severity": raw_sev},
        )
