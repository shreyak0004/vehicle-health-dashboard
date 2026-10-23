
from datetime import datetime
import random

from ingestion.simulator import generate_trip


def run_trip(ambient, eff_factor):
    readings, events, _, _ = generate_trip(
        rng=random.Random(42),
        start_time=datetime(2026, 10, 19, 8, 0),
        duration_min=35,
        mode="city",
        soc=90.0,
        odometer=12000.0,
        ambient=ambient,
        eff_factor=eff_factor,
    )
    return readings


warm = run_trip(ambient=27.0, eff_factor=1.0)
cold = run_trip(ambient=10.0, eff_factor=1.25)

warm_efficiency = sum(r[5] for r in warm) / len(warm)
cold_efficiency = sum(r[5] for r in cold) / len(cold)

print("Warm-weather consumption:", round(warm_efficiency, 2), "Wh/km")
print("Cold-weather consumption:", round(cold_efficiency, 2), "Wh/km")

assert len(warm) == 35
assert len(cold) == 35
assert cold_efficiency > warm_efficiency

print("PASS: Cold-weather efficiency scenario works!")
