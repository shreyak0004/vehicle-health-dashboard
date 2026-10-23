"""Generates 21 days of coherent EV telemetry with planted scenarios.

Run from the project root:
    python -m ingestion.simulator
"""
import random
from datetime import datetime, timedelta

from database.db import init_db, get_connection

VEHICLE_ID = "EV-001"
BATTERY_KWH = 40.0        # battery capacity
DAYS = 21                 # how many days of history
OVERHEAT_DAYS_AGO = 9     # the overheating scenario happens this many days ago
COLD_WEEK_DAYS = 7        # the last 7 days are cold (efficiency drop scenario)
FMT = "%Y-%m-%d %H:%M:%S"

ADAS_REASONS = [
    "Driver took over steering",
    "Lane markings not detected",
    "Camera view obstructed",
    "Driver braked manually",
]

INSERT_READING = """
INSERT INTO vehicle_readings
(vehicle_id, timestamp, speed, battery_temp, battery_soc, energy_wh_per_km,
 driving_mode, odometer_km, ambient_temp, range_km)
VALUES (?,?,?,?,?,?,?,?,?,?)
"""
INSERT_EVENT = """
INSERT INTO vehicle_events (vehicle_id, timestamp, event_type, severity, description)
VALUES (?,?,?,?,?)
"""


def generate_trip(
    rng, start_time, duration_min, mode, soc, odometer,
    ambient, eff_factor, overheat=False, adas_count=0,
    low_battery=False
):
    """Simulate one trip, one reading per minute.

    Returns (readings, events, final_soc, final_odometer).
    eff_factor > 1 means the car uses more energy (e.g. cold weather).
    """
    readings, events = [], []
    batt_temp = ambient + 10               # battery starts a little warmer than outside
    ramp_start = duration_min - 25         # overheating begins 25 min before trip end
    adas_minutes = set(rng.sample(range(5, duration_min), adas_count))
    elevated_logged = False
    warning_logged = False

    for minute in range(duration_min):
        ts = (start_time + timedelta(minutes=minute)).strftime(FMT)

        # Speed and base energy use depend on the driving mode
        if mode == "city":
            speed = max(0.0, rng.gauss(35, 12))
            base_wh = 135
        else:
            speed = max(60.0, rng.gauss(95, 8))
            base_wh = 165

        # Energy used this minute -> battery charge drops accordingly
        wh_per_km = base_wh * eff_factor * rng.uniform(0.95, 1.05)
        km = speed / 60
        soc -= (wh_per_km * km) / (BATTERY_KWH * 1000) * 100
        # Plant a low-battery scenario for predictable testing
        if low_battery:
            soc = min(soc, 14.0)
        soc = max(1.0, soc)
        odometer += km

        # Battery temperature slowly follows a target temperature
        target = ambient + 4 + speed * 0.08
        if overheat and minute >= ramp_start:
            target += (minute - ramp_start + 1) * 1.2     # planted overheating ramp
        batt_temp += (target - batt_temp) * 0.15 + rng.uniform(-0.2, 0.2)

        range_km = max(0.0, (soc / 100) * BATTERY_KWH * 1000 / (150 * eff_factor))

        readings.append((
            VEHICLE_ID, ts, round(speed, 1), round(batt_temp, 1), round(soc, 2),
            round(wh_per_km, 1), mode, round(odometer, 1), round(ambient, 1),
            round(range_km, 1),
        ))

        # Events
        if batt_temp >= 45 and not elevated_logged:
            elevated_logged = True
            events.append((VEHICLE_ID, ts, "BATTERY_TEMP_ELEVATED", "info",
                           f"Battery temperature above 45 C ({batt_temp:.1f} C)"))
        if batt_temp >= 55 and not warning_logged:
            warning_logged = True
            events.append((VEHICLE_ID, ts, "BATTERY_OVERHEAT_WARNING", "critical",
                           f"Battery overheating warning at {batt_temp:.1f} C"))
        # Low-battery warning
        if soc <= 15 and not any(
            event[2] == "LOW_BATTERY_WARNING" for event in events
        ):
            events.append((
                VEHICLE_ID, ts, "LOW_BATTERY_WARNING", "warning",
                f"Battery state of charge is low ({soc:.1f}%)"
            ))

        if minute in adas_minutes:
            events.append((VEHICLE_ID, ts, "ADAS_DISENGAGEMENT", "warning",
                           rng.choice(ADAS_REASONS)))

    return readings, events, soc, odometer


def generate_history(days=DAYS, seed=42):
    """Build the full history. The seed makes it repeatable."""
    rng = random.Random(seed)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    all_readings, all_events = [], []
    odometer = 12000.0

    for days_ago in range(days, 0, -1):           # oldest day first, ends yesterday
        day = today - timedelta(days=days_ago)
        cold = days_ago <= COLD_WEEK_DAYS
        ambient = rng.uniform(8, 14) if cold else rng.uniform(24, 30)
        eff = 1.25 if cold else 1.0               # 25% more energy use when cold
        soc = rng.uniform(88, 100)                # car is charged overnight

        # Exactly 2 ADAS events yesterday, otherwise occasionally 1
        adas_total = 2 if days_ago == 1 else (1 if rng.random() < 0.25 else 0)

        # Morning city trip
        low_battery = (days_ago == 3)

        r_city, e_city, soc, odometer = generate_trip(
            rng, day.replace(hour=8), rng.randint(30, 45), "city",
            soc, odometer, ambient + rng.uniform(-1, 1), eff,
            low_battery=low_battery)
        all_readings += r_city
        all_events += e_city
        # Recharge after the morning low-battery test scenario
        if low_battery:
            soc = rng.uniform(88, 100)
        # Evening highway trip (with the overheating scenario on one day)
        overheat = (days_ago == OVERHEAT_DAYS_AGO)
        duration = 60 if overheat else rng.randint(40, 60)
        r_hwy, e_hwy, soc, odometer = generate_trip(
            rng, day.replace(hour=18), duration, "highway",
            soc, odometer, ambient + rng.uniform(-1, 1), eff,
            overheat=overheat, adas_count=adas_total)
        all_readings += r_hwy
        all_events += e_hwy

    return all_readings, all_events


def main():
    import argparse
    from database.db import get_db_path

    parser = argparse.ArgumentParser(description="Simulate vehicle telemetry and seed SQLite database.")
    parser.add_argument("--reset", action="store_true", help="Explicitly reset/recreate database before seeding.")
    parser.add_argument("--days", type=int, default=DAYS, help="Number of days to simulate (default: 21).")
    args = parser.parse_args()

    db_path = get_db_path()
    if db_path.exists() and not args.reset:
        print(f"Database already exists at {db_path}. Safe protection active: use --reset to re-seed.")
        return

    init_db(reset=args.reset)
    readings, events = generate_history(days=args.days)
    conn = get_connection()
    conn.executemany(INSERT_READING, readings)
    conn.executemany(INSERT_EVENT, events)
    conn.commit()
    conn.close()
    print(f"Saved {len(readings)} readings and {len(events)} events (reset={args.reset}).")


if __name__ == "__main__":
    main()