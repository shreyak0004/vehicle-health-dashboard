
from datetime import datetime
import random

from ingestion.simulator import generate_trip

readings, events, final_soc, _ = generate_trip(
    rng=random.Random(42),
    start_time=datetime(2026, 10, 19, 8, 0),
    duration_min=35,
    mode="city",
    soc=90.0,
    odometer=12000.0,
    ambient=20.0,
    eff_factor=1.0,
    low_battery=True,
)

low_battery_events = [
    event for event in events
    if event[2] == "LOW_BATTERY_WARNING"
]

print("Readings generated:", len(readings))
print("Final battery SOC:", round(final_soc, 2), "%")
print("Low-battery warnings:", len(low_battery_events))

assert readings, "No readings generated"
assert low_battery_events, "Low-battery warning was not generated"
assert all(row[4] <= 15 for row in readings), "SOC exceeded 15%"
print("PASS: Low-battery scenario works!")
