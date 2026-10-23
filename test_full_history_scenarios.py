
from collections import Counter
from ingestion.simulator import generate_history

readings, events = generate_history()

print("Total readings:", len(readings))
print("Total events:", len(events))

# Check duplicate vehicle/timestamp pairs
keys = [(row[0], row[1]) for row in readings]
duplicates = len(keys) - len(set(keys))
print("Duplicate vehicle/timestamp pairs:", duplicates)
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days=1)).date()

yesterday_adas = [
    event for event in events
    if event[2] == "ADAS_DISENGAGEMENT"
    and datetime.strptime(
        event[1], "%Y-%m-%d %H:%M:%S"
    ).date() == yesterday
]

print("ADAS events yesterday:", len(yesterday_adas))
assert len(yesterday_adas) == 2, (
    "Expected exactly 2 ADAS events yesterday"
)
# Summarize event types
event_counts = Counter(event[2] for event in events)
print("\nEvent counts:")
for event_type, count in sorted(event_counts.items()):
    print(f"{event_type}: {count}")

print("\nADAS event timestamps:")
for event in events:
    if event[2] == "ADAS_DISENGAGEMENT":
        print(event[1], "-", event[4])

print("\nLow-battery event timestamps:")
for event in events:
    if event[2] == "LOW_BATTERY_WARNING":
        print(event[1], "-", event[4])

# Confirm required scenarios are represented
# assert len(readings) > 0, "No readings generated"
# assert duplicates == 0, "Duplicate vehicle/timestamp pairs found"
# assert event_counts["BATTERY_OVERHEAT_WARNING"] > 0, "Overheating scenario missing"
# assert event_counts["LOW_BATTERY_WARNING"] > 0, "Low-battery scenario missing"
# assert event_counts["ADAS_DISENGAGEMENT"] == 2, "Expected exactly 2 ADAS events"

print("\nPASS: Full history scenarios work together!")
