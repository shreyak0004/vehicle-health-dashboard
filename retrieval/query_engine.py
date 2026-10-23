
"""Turns a natural-language question into exact facts from the database."""
import re
from datetime import datetime, timedelta

from analytics import queries as A

FMT = "%Y-%m-%d %H:%M:%S"

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Order matters: the first matching group wins.
COLUMN_KEYWORDS = [
    ("battery_temp", ["temperature", "temp", "overheat", "hot"]),
    ("range_km", ["range"]),
    ("energy_wh_per_km", ["consumption", "efficiency", "energy", "wh/km"]),
    ("speed", ["speed", "fast"]),
    ("battery_soc", ["soc", "charge", "battery"]),
]

HELP_TEXT = (
    "I can answer questions about highest/lowest values, trends over time, "
    "city vs highway comparisons, events such as ADAS disengagements, "
    "unusual readings, and what happened before a warning."
)


# ---------- 1. Understanding the question ----------

def parse_time_range(question):
    """Return (start, end, label). The end timestamp is exclusive."""
    q = question.lower()
    midnight = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if "yesterday" in q:
        return (
            (midnight - timedelta(days=1)).strftime(FMT),
            midnight.strftime(FMT),
            "yesterday",
        )

    if "today" in q:
        return (
            midnight.strftime(FMT),
            (midnight + timedelta(days=1)).strftime(FMT),
            "today",
        )

    match = re.search(
        r"(last\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+(day|week|month)s?",
        q,
    )

    if match:
        token = match.group(2)
        number = int(token) if token.isdigit() else NUMBER_WORDS[token]
        unit = match.group(3)
        days = number * {"day": 1, "week": 7, "month": 30}[unit]

        return (
            (midnight - timedelta(days=days)).strftime(FMT),
            midnight.strftime(FMT),
            f"the last {days} days",
        )

    if "week" in q:
        return (
            (midnight - timedelta(days=7)).strftime(FMT),
            midnight.strftime(FMT),
            "the last 7 days",
        )

    if "month" in q:
        return (
            (midnight - timedelta(days=30)).strftime(FMT),
            midnight.strftime(FMT),
            "the last 30 days",
        )

    return None, None, "all available data"


UNSUPPORTED_SIGNALS = [
    ("tyre_pressure", ["tyre", "tire", "pressure", "psi", "bar", "tpms"], "Tyre pressure"),
    ("motor_rpm", ["rpm", "motor speed", "engine speed", "revs"], "Motor RPM"),
    ("oil_level", ["oil", "engine oil", "motor oil"], "Engine oil level"),
    ("cabin_climate", ["cabin", "air conditioning", "ac temp", "hvac", "climate", "interior temp", "humidity"], "Cabin climate"),
    ("steering_angle", ["steering angle", "wheel angle"], "Steering angle"),
    ("brake_system", ["brake pad", "brake wear", "brake fluid"], "Brake condition"),
    ("coolant_level", ["coolant", "radiator"], "Coolant level"),
    ("fuel_system", ["fuel level", "fuel tank", "gas level", "petrol", "diesel", "fuel gauge"], "Fuel level"),
    ("transmission", ["transmission", "gearbox", "gear ratio"], "Transmission"),
]

CONTROL_COMMANDS = [
    "accelerate", "brake", "steer", "turn left", "turn right",
    "speed up", "slow down", "unlock", "lock doors", "open trunk",
    "honk", "flash lights", "engage autopilot", "apply brake", "apply brakes"
]


def detect_unsupported_signal(question):
    q = question.lower()
    for sig_key, keywords, display_name in UNSUPPORTED_SIGNALS:
        if any(kw in q for kw in keywords):
            return sig_key, display_name
    return None


def detect_control_command(question):
    q = question.lower()
    is_query = any(w in q for w in ["did", "was", "how", "what", "when", "why", "were", "show", "is", "explain"])
    if not is_query and any(cmd in q for cmd in CONTROL_COMMANDS):
        return True
    return False


def detect_column(question):
    q = question.lower()

    for column, words in COLUMN_KEYWORDS:
        if any(word in q for word in words):
            return column

    return None


def detect_intent(question):
    q = question.lower()

    if detect_control_command(question):
        return "control_refusal"

    if detect_unsupported_signal(question):
        return "unsupported_signal"

    if any(word in q for word in ["before", "led to", "caused", "overheat", "overheating"]):
        return "event_investigation"

    if any(word in q for word in ["average", "mean", "typical"]):
        return "average"

    if "compare" in q or ("city" in q and "highway" in q):
        return "compare"

    if any(word in q for word in ["unusual", "anomal", "abnormal", "strange"]):
        return "anomaly"

    if (
        any(word in q for word in ["largest", "biggest", "most", "worst"])
        and any(
            word in q
            for word in ["drop", "decrease", "increase", "change", "jump"]
        )
    ):
        return "largest_change"

    if any(
        word in q
        for word in ["adas", "disengage", "event", "warning", "alert", "diagnostic", "dtc", "log", "incident", "fault"]
    ):
        return "events"

    if any(
        word in q
        for word in ["highest", "maximum", "peak", "lowest", "minimum"]
    ):
        return "maxmin"

    if any(
        word in q
        for word in [
            "why", "trend", "changed", "change", "reduced",
            "decrease", "increase", "how has", "how is", "dropped",
            "doing", "status", "health", "condition"
        ]
    ):
        return "trend"

    return "unknown"


def detect_event_type(question):
    q = question.lower()

    if "adas" in q or "disengage" in q:
        return "ADAS_DISENGAGEMENT"

    if "overheat" in q:
        return "BATTERY_OVERHEAT_WARNING"

    if "low battery" in q or "charge low" in q or "soc low" in q:
        return "LOW_BATTERY_WARNING"

    return None


# ---------- Helpers ----------

def _result(intent, label, facts, rows=None, chart=None):
    return {
        "intent": intent,
        "time_range": label,
        "facts": facts,
        "rows": rows or [],
        "chart": chart,
    }


def _fmt(column, value):
    name, unit = A.COLUMNS[column]
    return f"{value:.1f} {unit}"


def _daily_chart(column, start, end):
    days = A.daily_averages(column, start, end)

    if len(days) < 2:
        return None

    name, unit = A.COLUMNS[column]

    return {
        "labels": [day["day"] for day in days],
        "values": [round(day["value"], 1) for day in days],
        "label": f"Daily average {name} ({unit})",
    }


# ---------- 2. Handlers ----------

def handle_maxmin(question, start, end, label):
    column = detect_column(question)

    if column is None:
        return _result("maxmin", label, [HELP_TEXT])

    highest = not any(
        word in question for word in ["lowest", "minimum"]
    )
    row = A.get_extreme(column, highest, start, end)

    if row is None:
        return _result("maxmin", label, ["No readings found for this time range."])

    direction = "Highest" if highest else "Lowest"
    name, _ = A.COLUMNS[column]

    facts = [
        f"{direction} {name}: {_fmt(column, row['value'])} "
        f"at {row['timestamp']}."
    ]

    return _result("maxmin", label, facts, rows=[row])


def handle_average(question, start, end, label):
    column = detect_column(question)

    if column is None:
        return _result("average", label, [HELP_TEXT])

    avg_val = A.get_average(column, start, end)

    if avg_val is None:
        return _result("average", label, ["No readings found for this time range."])

    name, unit = A.COLUMNS[column]
    facts = [
        f"Average {name} in {label}: {avg_val:.1f} {unit}."
    ]

    return _result("average", label, facts, rows=[{"average": avg_val, "column": column}])


def handle_trend(question, start, end, label):
    column = detect_column(question)

    if column is None:
        return _result("trend", label, [HELP_TEXT])

    result = A.trend(column, start, end)

    if result is None:
        return _result(
            "trend", label,
            ["Not enough daily readings to calculate a trend."],
        )

    name, unit = A.COLUMNS[column]
    change = result["percent_change"]
    direction = "increased" if change >= 0 else "decreased"

    facts = [
        f"Average {name} in the first half: "
        f"{result['first_half_avg']:.1f} {unit}.",
        f"Average {name} in the second half: "
        f"{result['second_half_avg']:.1f} {unit}.",
        f"Across the two halves, {name} {direction} by "
        f"{abs(change):.1f}%.",
    ]

    # Correlated sequence inquiry (cold ambient temperature -> higher consumption -> reduced range)
    if column in ("range_km", "energy_wh_per_km", "ambient_temp") or any(
        w in question for w in ["why", "cause", "drop", "reduc", "explain", "cold", "reason"]
    ):
        corr = A.analyze_cold_weather_correlation(start, end)
        if corr:
            facts.append(f"Correlated sequence: {corr['what_changed']}")
            facts.append(f"Transition timing: {corr['when_changed']}")
            facts.append(f"Supporting readings: {corr['readings'][0]} {corr['readings'][1]} {corr['readings'][2]}")
            facts.append(f"{corr['observed_vs_explanation']['observed']}")
            facts.append(f"{corr['observed_vs_explanation']['explanation']}")
    elif column == "range_km":
        energy = A.trend("energy_wh_per_km", start, end)
        ambient = A.trend("ambient_temp", start, end)

        if energy:
            facts.append(
                f"Energy consumption changed by "
                f"{energy['percent_change']:.1f}% across the two halves."
            )

        if ambient:
            facts.append(
                f"Outside temperature changed by "
                f"{ambient['percent_change']:.1f}% across the two halves."
            )

    return _result(
        "trend", label, facts,
        rows=result["days"],
        chart=_daily_chart(column, start, end),
    )


def handle_compare(question, start, end, label):
    column = detect_column(question)

    if column is None:
        data = A.compare_city_vs_highway(start, end)
        has_data = any(v["city"] is not None or v["highway"] is not None for v in data.values())
        if not has_data:
            return _result("compare", label, [f"No city or highway readings found for {label}."])

        facts = [f"Comparison of city vs highway driving for {label}:"]

        sp = data["speed"]
        if sp["city"] is not None and sp["highway"] is not None:
            diff_spd = sp["highway"] - sp["city"]
            facts.append(
                f"Average speed: {sp['city']:.1f} km/h in city vs {sp['highway']:.1f} km/h on highway "
                f"({abs(diff_spd):.1f} km/h {'faster' if diff_spd >= 0 else 'slower'} on highway)."
            )

        en = data["energy_wh_per_km"]
        if en["city"] is not None and en["highway"] is not None:
            diff_en = en["highway"] - en["city"]
            pct_en = en["pct_diff"]
            facts.append(
                f"Energy consumption: {en['city']:.1f} Wh/km in city vs {en['highway']:.1f} Wh/km on highway "
                f"({abs(diff_en):.1f} Wh/km / {abs(pct_en):.1f}% {'higher' if diff_en >= 0 else 'lower'} on highway)."
            )

        bt = data["battery_temp"]
        if bt["city"] is not None and bt["highway"] is not None:
            diff_bt = bt["highway"] - bt["city"]
            facts.append(
                f"Battery temperature: {bt['city']:.1f} °C in city vs {bt['highway']:.1f} °C on highway "
                f"({abs(diff_bt):.1f} °C {'warmer' if diff_bt >= 0 else 'cooler'} on highway)."
            )

        soc = data["battery_soc"]
        if soc["city"] is not None and soc["highway"] is not None:
            diff_soc = soc["highway"] - soc["city"]
            facts.append(
                f"Battery charge level (SOC): {soc['city']:.1f}% average in city vs {soc['highway']:.1f}% on highway."
            )

        chart = {
            "labels": ["City", "Highway"],
            "speed": [round(sp["city"] or 0, 1), round(sp["highway"] or 0, 1)],
            "energy_wh_per_km": [round(en["city"] or 0, 1), round(en["highway"] or 0, 1)],
            "battery_temp": [round(bt["city"] or 0, 1), round(bt["highway"] or 0, 1)],
            "battery_soc": [round(soc["city"] or 0, 1), round(soc["highway"] or 0, 1)],
        }
        return _result("compare", label, facts, rows=[data], chart=chart)

    averages = A.compare_modes(column, start, end)
    name, unit = A.COLUMNS[column]

    facts = [f"Comparing {name} for {label}:"]

    for mode in ("city", "highway"):
        value = averages[mode]
        if value is not None:
            facts.append(f"Average {name} in {mode} mode: {value:.1f} {unit}.")
        else:
            facts.append(f"No readings available for {mode} mode.")

    if all(averages[mode] is not None for mode in ("city", "highway")):
        difference = averages["highway"] - averages["city"]
        facts.append(
            f"Highway minus city difference: {difference:.1f} {unit}."
        )

    if column in ("speed", "energy_wh_per_km"):
        other_col = "energy_wh_per_km" if column == "speed" else "speed"
        other_avg = A.compare_modes(other_col, start, end)
        other_name, other_unit = A.COLUMNS[other_col]
        if other_avg["city"] is not None and other_avg["highway"] is not None:
            facts.append(
                f"Context ({other_name}): {other_avg['city']:.1f} {other_unit} in city vs {other_avg['highway']:.1f} {other_unit} on highway."
            )

    return _result("compare", label, facts, rows=[averages])


def handle_events(question, start, end, label):
    event_type = detect_event_type(question)
    events = A.get_events(event_type, start, end)

    if not events:
        return _result(
            "events", label,
            ["No matching events were found in this time range."],
        )

    facts = [
        f"Found {len(events)} matching event(s) in {label}."
    ]

    for event in events[:10]:
        facts.append(
            f"{event['timestamp']}: {event['event_type']} "
            f"({event['severity']}) — {event['description']}."
        )

    return _result("events", label, facts, rows=events)



def handle_largest_change(question, start, end, label):
    column = detect_column(question)

    if column is None:
        return _result("largest_change", label, [HELP_TEXT])

    direction = (
        "decrease"
        if any(word in question.lower()
               for word in ["drop", "decrease", "decline", "reduced", "reduction"])
        else "increase"
    )

    result = A.largest_daily_change(column, start, end, direction)

    if result is None:
        return _result(
            "largest_change",
            label,
            [f"No daily {direction} in {A.COLUMNS[column][0]} was found "
             "in the selected time range."],
        )

    name, unit = A.COLUMNS[column]

    facts = [
        f"Largest daily {direction} in {name} occurred on {result['day']}.",
        f"Previous daily average: {result['from']:.1f} {unit}.",
        f"New daily average: {result['to']:.1f} {unit}.",
        f"Size of {direction}: {result['change']:.1f} {unit}.",
    ]

    return _result("largest_change", label, facts, rows=[result])



def handle_anomaly(question, start, end, label):
    unsupported = detect_unsupported_signal(question)
    if unsupported:
        return handle_unsupported_signal(question, start, end, label)

    column = detect_column(question)

    if column is None:
        column = "battery_temp"
        name, unit = A.COLUMNS[column]
        scope_note = f"Checked {name} (default telemetry signal) using a 2-standard-deviation threshold."
    else:
        name, unit = A.COLUMNS[column]
        scope_note = f"Checked {name} readings using a 2-standard-deviation threshold."

    result = A.find_anomalies(column, start, end, z=2.0)

    facts = [
        scope_note,
        f"Detected {result['count']} unusual reading(s).",
    ]

    if result["mean"] is not None:
        facts.append(f"Mean {name}: {result['mean']:.1f} {unit}.")

    for row in result["examples"]:
        facts.append(
            f"Unusual reading: {row['value']:.1f} {unit} "
            f"at {row['timestamp']} (z-score {row['zscore']:.2f})."
        )

    return _result(
        "anomaly", label, facts, rows=result["examples"]
    )


def handle_unsupported_signal(question, start, end, label):
    detected = detect_unsupported_signal(question)
    display_name = detected[1] if detected else "Requested"
    facts = [
        f"{display_name} data is not available in the current vehicle telemetry dataset.",
        "The current schema records speed, battery temperature, state of charge (SOC), energy consumption, driving mode, odometer, and outside temperature.",
        f"Cannot evaluate readings, trends, or anomalies for {display_name.lower()}."
    ]
    return {
        "intent": "unsupported_signal",
        "time_range": label,
        "facts": facts,
        "rows": [],
        "chart": None,
        "unsupported": True,
        "requested_signal": detected[0] if detected else "unknown",
    }


def handle_control_refusal(question, start, end, label):
    facts = [
        "VehicleGPT is a read-only diagnostics and telemetry assistant.",
        "VehicleGPT cannot execute driving, steering, braking, acceleration, or vehicle control commands.",
        "Safety-critical vehicle controls must be operated directly by the certified driver or vehicle ECU."
    ]
    return {
        "intent": "control_refusal",
        "time_range": label,
        "facts": facts,
        "rows": [],
        "chart": None,
        "read_only_protection": True,
    }


def handle_event_investigation(question, start, end, label):
    event_type = detect_event_type(question) or "BATTERY_OVERHEAT_WARNING"
    events = A.get_events(event_type, start, end)

    if not events:
        # If no date was specified, look across all available data.
        if start is None and end is None:
            events = A.get_events(event_type)

    if not events:
        return _result(
            "event_investigation", label,
            ["No matching warning was found in the requested time range."],
        )

    event = events[-1]
    before = A.get_readings_before_event(event["timestamp"], minutes=30)

    if not before:
        return _result(
            "event_investigation", label,
            [f"Warning at {event['timestamp']}: {event['description']}.",
             "No preceding readings were available."],
            rows=events,
        )

    first = before[0]
    last = before[-1]
    avg_speed = sum(row["speed"] for row in before) / len(before)
    max_speed = max(row["speed"] for row in before)

    facts = [
        f"Warning at {event['timestamp']}: {event['description']}.",
        f"Battery temperature changed from {first['battery_temp']:.1f} °C "
        f"to {last['battery_temp']:.1f} °C in the preceding readings.",
        f"Average speed in that window was {avg_speed:.1f} km/h "
        f"(maximum {max_speed:.1f} km/h).",
        f"Outside temperature at the end of the window was "
        f"{last['ambient_temp']:.1f} °C.",
        "The available data shows a temperature increase before the warning, but does not confirm a mechanical or electrical root cause.",
    ]

    chart = {
        "labels": [row["timestamp"][11:16] for row in before],
        "values": [row["battery_temp"] for row in before],
        "label": "Battery temperature before the warning (°C)",
    }

    return _result(
        "event_investigation", label, facts,
        rows=events, chart=chart,
    )


HANDLERS = {
    "maxmin": handle_maxmin,
    "average": handle_average,
    "trend": handle_trend,
    "compare": handle_compare,
    "events": handle_events,
    "largest_change": handle_largest_change,
    "anomaly": handle_anomaly,
    "event_investigation": handle_event_investigation,
    "unsupported_signal": handle_unsupported_signal,
    "control_refusal": handle_control_refusal,
}


# ---------- 3. Public functions ----------

def answer_question(question):
    """Convert a question into exact facts from the vehicle database."""
    start, end, label = parse_time_range(question)
    intent = detect_intent(question)
    handler = HANDLERS.get(intent)

    if handler is None:
        return _result("unknown", label, [HELP_TEXT])

    return handler(question.lower(), start, end, label)


def evidence_text(result):
    """Format facts for the local LLM or fallback response."""
    return "\n".join(f"- {fact}" for fact in result["facts"])
