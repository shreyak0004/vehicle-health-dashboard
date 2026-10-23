"""Camera Perception Metadata Adapter.

Ingests derived computer vision metadata (lane confidence, lens obstruction, optical clarity)
without loading heavy raw pixel streams onto resource-constrained edge compute.
"""
from typing import Dict, Any, Optional
from ingestion.common_schema import NormalizedEvent, SourceType
from ingestion.normalizer import normalize_timestamp


class CameraMetadataAdapter:
    """Ingests optical perception metadata from forward-facing automotive camera pipelines."""

    def __init__(self, default_vehicle_id: str = "EV-001"):
        self.default_vehicle_id = default_vehicle_id

    def parse_metadata(self, frame_meta: Dict[str, Any]) -> Optional[NormalizedEvent]:
        """Parses a camera perception metadata record.

        Structure:
        {
            "timestamp": "2026-10-21 18:18:00",
            "camera_id": "front_narrow_fov",
            "lens_obstructed": True,
            "lane_confidence": 0.12,
            "lux": 15.0
        }
        """
        ts = normalize_timestamp(frame_meta.get("timestamp"))
        vehicle_id = frame_meta.get("vehicle_id", self.default_vehicle_id)
        obstructed = frame_meta.get("lens_obstructed", False)
        lane_conf = frame_meta.get("lane_confidence", 1.0)
        camera_id = frame_meta.get("camera_id", "front_main")

        meta = {
            "camera_id": camera_id,
            "lane_confidence": lane_conf,
            "ambient_lux": frame_meta.get("lux"),
        }

        # If camera view is blinded or obstructed, generate an ADAS alert
        if obstructed:
            return NormalizedEvent(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.CAMERA_METADATA,
                event_type="ADAS_DISENGAGEMENT",
                severity="warning",
                description="Camera view obstructed",
                metadata=meta,
            )
        elif lane_conf < 0.25:
            return NormalizedEvent(
                vehicle_id=vehicle_id,
                timestamp=ts,
                source_type=SourceType.CAMERA_METADATA,
                event_type="ADAS_DISENGAGEMENT",
                severity="warning",
                description="Lane markings not detected",
                metadata=meta,
            )

        return None
