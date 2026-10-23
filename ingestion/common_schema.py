"""Common internal data schema for multi-source vehicle ingestion.

Normalizes heterogeneous automotive inputs (CAN, SOME/IP, Android VHAL, QNX, ADAS,
Camera perception metadata, Diagnostics) into unified telemetry and event representations.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class SourceType(str, Enum):
    CAN = "CAN"
    CAN_FD = "CAN_FD"
    SOME_IP = "SOME_IP"
    ANDROID_VHAL = "ANDROID_VHAL"
    QNX_LOG = "QNX_LOG"
    ADAS = "ADAS"
    CAMERA_METADATA = "CAMERA_METADATA"
    DIAGNOSTIC_LOG = "DIAGNOSTIC_LOG"
    SIMULATOR = "SIMULATOR"


@dataclass
class NormalizedTelemetry:
    """Unified representation of continuous vehicle sensor and state signals."""
    vehicle_id: str
    timestamp: str                                  # Format: YYYY-MM-DD HH:MM:SS
    source_type: SourceType
    speed: Optional[float] = None                  # km/h
    battery_temp: Optional[float] = None           # degrees Celsius
    battery_soc: Optional[float] = None            # percent (0 - 100)
    energy_wh_per_km: Optional[float] = None       # Wh/km
    driving_mode: Optional[str] = None             # 'city' | 'highway'
    odometer_km: Optional[float] = None            # km
    ambient_temp: Optional[float] = None           # degrees Celsius
    range_km: Optional[float] = None               # km
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedEvent:
    """Unified representation of discrete vehicle alerts, diagnostic codes, and events."""
    vehicle_id: str
    timestamp: str                                  # Format: YYYY-MM-DD HH:MM:SS
    source_type: SourceType
    event_type: str                                # e.g. BATTERY_OVERHEAT_WARNING, ADAS_DISENGAGEMENT, DTC_LOGGED
    severity: str                                  # 'info' | 'warning' | 'critical'
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
