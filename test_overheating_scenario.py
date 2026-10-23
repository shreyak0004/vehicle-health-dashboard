
from datetime import datetime
import random

from ingestion.simulator import generate_trip

readings, events, final_soc, _ = generate_trip(
    rng=random.Random(42),
    start_time=datetime(2026, 10, 13, 18, 0),
    duration_min=60,
    mode="highway",
    soc=90.0,
    odometer=12000.0,
    ambient=25.0,
    eff_factor=1.0,
    overheat=True,
)

overheat_events = [
    event for event in events
    if event[2] == "BATTERY_OVERHEAT_WARNING"
]

max_temp = max(row[3] for row in readings)

print("Readings generated:", len(readings))
print("Maximum battery temperature:", max_temp, "°C")
print("Overheat warnings:", len(overheat_events))
print("First timestamp:", readings[0][1])
print("Last timestamp:", readings[-1][1])
print("Unique timestamps:", len(set(row[1] for row in readings)))
print("First 5 timestamps:", [row[1] for row in readings[:5]])
print("Last 5 timestamps:", [row[1] for row in readings[-5:]])

assert len(readings) == 60
assert max_temp >= 55, "Overheating temperature was not reached"
assert overheat_events, "Overheat warning was not generated"

print("PASS: Overheating scenario works!")
