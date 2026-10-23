"""Exact calculations on the vehicle database. No AI in this file."""
import statistics
from datetime import datetime, timedelta

from database.db import get_readonly_connection

FMT = "%Y-%m-%d %H:%M:%S"

# Allowed columns -> (friendly name, unit). Also protects against SQL injection,
# because we only ever put column names from this list into a query.
COLUMNS = {
    "speed":            ("speed", "km/h"),
    "battery_temp":     ("battery temperature", "°C"),
    "battery_soc":      ("battery charge level", "%"),
    "energy_wh_per_km": ("energy consumption", "Wh/km"),
    "range_km":         ("estimated range", "km"),
    "ambient_temp":     ("outside temperature", "°C"),
}


def _check(column):
    if column not in COLUMNS:
        raise ValueError(f"Unknown column: {column}")


def _range(start, end):
    """If no time range is given, use everything."""
    return start or "0000-01-01 00:00:00", end or "9999-12-31 23:59:59"


def _rows(sql, params=()):
    conn = get_readonly_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_extreme(column, highest=True, start=None, end=None):
    """The highest (or lowest) value and when it happened."""
    _check(column)
    s, e = _range(start, end)
    order = "DESC" if highest else "ASC"
    rows = _rows(
        f"SELECT timestamp, {column} AS value FROM vehicle_readings "
        f"WHERE timestamp >= ? AND timestamp < ? ORDER BY {column} {order} LIMIT 1",
        (s, e))
    return rows[0] if rows else None


def get_average(column, start=None, end=None, mode=None):
    """Average of a column, optionally only for 'city' or 'highway'."""
    _check(column)
    s, e = _range(start, end)
    sql = (f"SELECT AVG({column}) AS avg FROM vehicle_readings "
           f"WHERE timestamp >= ? AND timestamp < ?")
    params = [s, e]
    if mode:
        sql += " AND driving_mode = ?"
        params.append(mode)
    return _rows(sql, params)[0]["avg"]


def compare_modes(column, start=None, end=None):
    """Average of a column for city vs highway."""
    return {m: get_average(column, start, end, m) for m in ("city", "highway")}


def compare_city_vs_highway(start=None, end=None):
    """Compares speed, energy consumption, battery temp, and battery SOC between city and highway driving."""
    columns = ["speed", "energy_wh_per_km", "battery_temp", "battery_soc"]
    result = {}
    for col in columns:
        averages = compare_modes(col, start, end)
        city_val = averages.get("city")
        hwy_val = averages.get("highway")
        diff = (hwy_val - city_val) if (city_val is not None and hwy_val is not None) else None
        pct_diff = ((hwy_val - city_val) / city_val * 100) if (city_val and hwy_val is not None) else None
        result[col] = {
            "city": city_val,
            "highway": hwy_val,
            "diff": diff,
            "pct_diff": pct_diff,
            "unit": COLUMNS[col][1],
            "name": COLUMNS[col][0],
        }
    return result


def analyze_cold_weather_correlation(start=None, end=None):
    """Correlated fault scenario: Cold ambient temperature -> higher energy consumption -> reduced estimated range.

    Identifies:
    1. What changed (range reduction, consumption increase).
    2. When did it change (transition date).
    3. Which readings support the observation (ambient temp, Wh/km, range_km values).
    4. Observed telemetry versus possible causal explanations.
    """
    days_ambient = daily_averages("ambient_temp", start, end)
    days_energy = daily_averages("energy_wh_per_km", start, end)
    days_range = daily_averages("range_km", start, end)

    if len(days_ambient) < 2:
        return None

    # Find the day of largest ambient drop
    largest_drop = largest_daily_change("ambient_temp", start, end, direction="decrease")
    transition_date = largest_drop["day"] if largest_drop else days_ambient[len(days_ambient) // 2]["day"]

    # Split into baseline (days before transition) and cold period (transition day onwards)
    warm_ambient = [d["value"] for d in days_ambient if d["day"] < transition_date]
    cold_ambient = [d["value"] for d in days_ambient if d["day"] >= transition_date]
    warm_energy = [d["value"] for d in days_energy if d["day"] < transition_date]
    cold_energy = [d["value"] for d in days_energy if d["day"] >= transition_date]
    warm_range = [d["value"] for d in days_range if d["day"] < transition_date]
    cold_range = [d["value"] for d in days_range if d["day"] >= transition_date]

    # Fallback to two halves if transition split is uneven (e.g. at the very boundary)
    if not warm_ambient or not cold_ambient:
        half = len(days_ambient) // 2
        transition_date = days_ambient[half]["day"]
        warm_ambient = [d["value"] for d in days_ambient[:half]]
        cold_ambient = [d["value"] for d in days_ambient[half:]]
        warm_energy = [d["value"] for d in days_energy[:half]]
        cold_energy = [d["value"] for d in days_energy[half:]]
        warm_range = [d["value"] for d in days_range[:half]]
        cold_range = [d["value"] for d in days_range[half:]]

    avg_warm_temp = statistics.mean(warm_ambient)
    avg_cold_temp = statistics.mean(cold_ambient)
    avg_warm_energy = statistics.mean(warm_energy)
    avg_cold_energy = statistics.mean(cold_energy)
    avg_warm_range = statistics.mean(warm_range)
    avg_cold_range = statistics.mean(cold_range)

    temp_drop = avg_warm_temp - avg_cold_temp
    wh_pct_increase = ((avg_cold_energy - avg_warm_energy) / avg_warm_energy * 100) if avg_warm_energy else 0.0
    range_pct_drop = ((avg_warm_range - avg_cold_range) / avg_warm_range * 100) if avg_warm_range else 0.0

    return {
        "transition_date": transition_date,
        "baseline": {
            "ambient_temp": avg_warm_temp,
            "energy_wh_per_km": avg_warm_energy,
            "range_km": avg_warm_range,
        },
        "cold_period": {
            "ambient_temp": avg_cold_temp,
            "energy_wh_per_km": avg_cold_energy,
            "range_km": avg_cold_range,
        },
        "changes": {
            "temp_drop": temp_drop,
            "wh_increase_pct": wh_pct_increase,
            "wh_diff": avg_cold_energy - avg_warm_energy,
            "range_drop_pct": range_pct_drop,
            "range_diff": avg_warm_range - avg_cold_range,
        },
        "what_changed": (
            f"Estimated driving range decreased by {abs(range_pct_drop):.1f}% "
            f"as energy consumption increased by {wh_pct_increase:.1f}%."
        ),
        "when_changed": (
            f"The transition occurred on {transition_date}, coinciding with outside ambient temperature dropping."
        ),
        "readings": [
            f"Outside ambient temperature dropped from {avg_warm_temp:.1f} °C to {avg_cold_temp:.1f} °C (-{temp_drop:.1f} °C).",
            f"Energy consumption rose from {avg_warm_energy:.1f} Wh/km to {avg_cold_energy:.1f} Wh/km (+{avg_cold_energy - avg_warm_energy:.1f} Wh/km).",
            f"Estimated range fell from {avg_warm_range:.1f} km to {avg_cold_range:.1f} km (-{avg_warm_range - avg_cold_range:.1f} km).",
        ],
        "observed_vs_explanation": {
            "observed": (
                "Observed telemetry: Sensor readings directly record lower ambient temperatures "
                "coinciding with elevated Wh/km energy consumption and reduced estimated range."
            ),
            "explanation": (
                "Possible explanation: Cold ambient conditions increase battery internal resistance "
                "and auxiliary cabin heating demand; vehicle telemetry records overall consumption but does not meter HVAC sub-circuits."
            ),
        },
    }



def daily_averages(column, start=None, end=None):
    """[{'day': '2025-01-01', 'value': 12.3}, ...] one entry per day."""
    _check(column)
    s, e = _range(start, end)
    return _rows(
        f"SELECT substr(timestamp, 1, 10) AS day, AVG({column}) AS value "
        f"FROM vehicle_readings WHERE timestamp >= ? AND timestamp < ? "
        f"GROUP BY day ORDER BY day", (s, e))



def largest_daily_change(column, start=None, end=None, direction="increase"):
    """Find the largest actual day-to-day increase or decrease."""
    if direction not in ("increase", "decrease"):
        raise ValueError("direction must be 'increase' or 'decrease'")

    days = daily_averages(column, start, end)
    best = None

    for prev, cur in zip(days, days[1:]):
        difference = cur["value"] - prev["value"]

        if direction == "increase" and difference <= 0:
            continue
        if direction == "decrease" and difference >= 0:
            continue

        change = abs(difference)

        if best is None or change > best["change"]:
            best = {
                "day": cur["day"],
                "from": prev["value"],
                "to": cur["value"],
                "change": change,
            }

    return best



def trend(column, start=None, end=None):
    """Compare the first half of the days with the second half."""
    days = daily_averages(column, start, end)
    if len(days) < 2:
        return None
    half = len(days) // 2
    first = statistics.mean(d["value"] for d in days[:half])
    second = statistics.mean(d["value"] for d in days[half:])
    pct = (second - first) / first * 100 if first else 0.0
    return {"first_half_avg": first, "second_half_avg": second,
            "percent_change": pct, "days": days}


def get_events(event_type=None, start=None, end=None, limit=100):
    """Events in a time range, oldest first. Optionally filter by type."""
    s, e = _range(start, end)
    sql = ("SELECT id, timestamp, event_type, severity, description "
           "FROM vehicle_events WHERE timestamp >= ? AND timestamp < ?")
    params = [s, e]
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    sql += " ORDER BY timestamp LIMIT ?"
    params.append(limit)
    return _rows(sql, params)


def get_readings_before_event(event_timestamp, minutes=30):
    """All readings in the N minutes up to (and including) the event."""
    t = datetime.strptime(event_timestamp, FMT)
    start = (t - timedelta(minutes=minutes)).strftime(FMT)
    return _rows(
        "SELECT * FROM vehicle_readings WHERE timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp", (start, event_timestamp))


def find_anomalies(column, start=None, end=None, z=3.0):
    """Statistical anomaly detection.

    A reading is 'unusual' if it is more than z standard deviations away from
    the average. (z=3 is a common rule of thumb.)
    """
    _check(column)
    s, e = _range(start, end)
    rows = _rows(
        f"SELECT timestamp, {column} AS value FROM vehicle_readings "
        f"WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp", (s, e))
    if len(rows) < 10:
        return {"count": 0, "mean": None, "std": None, "examples": []}
    values = [r["value"] for r in rows]
    mean = statistics.mean(values)
    std = statistics.pstdev(values)
    if std == 0:
        return {"count": 0, "mean": mean, "std": std, "examples": []}
    flagged = [dict(r, zscore=(r["value"] - mean) / std)
               for r in rows if abs(r["value"] - mean) / std > z]
    flagged.sort(key=lambda r: abs(r["zscore"]), reverse=True)
    return {"count": len(flagged), "mean": mean, "std": std, "examples": flagged[:5]}