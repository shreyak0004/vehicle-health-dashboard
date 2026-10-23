
from datetime import datetime
import random

from ingestion.simulator import generate_trip

readings, events, _, _ = generate_trip(
    rng=random.Random(42),
    start_time=datetime(2026, 10, 19, 18, 0),
    duration_min=60,
    mode="highway",
    soc=90.0,
    odometer=12000.0,
    ambient=20.0,
    eff_factor=1.0,
    adas_count=2,
)

adas_events = [
    event for event in events
    if event[2] == "ADAS_DISENGAGEMENT"
]

print("Readings:", len(readings))
print("ADAS events:", len(adas_events))
for event in adas_events:
    print(event[1], "-", event[4])

assert len(readings) == 60
assert len(adas_events) == 2
print("PASS: ADAS scenario works!")
