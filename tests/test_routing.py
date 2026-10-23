
import pytest

from retrieval.query_engine import (
    detect_intent,
    detect_column,
    parse_time_range,
)


CASES = [
    ("Why has driving range reduced over the last two weeks?", "trend"),
    ("When did fuel efficiency show the largest drop?", "largest_change"),
    ("Show ADAS disengagement events from yesterday", "events"),
    ("What happened before the battery overheating warning?", "event_investigation"),
    ("Compare energy consumption between city and highway driving", "compare"),
    ("What was the highest battery temperature yesterday?", "maxmin"),
    ("How has battery temperature changed this week?", "trend"),
    ("Were there any unusual temperature readings?", "anomaly"),
    ("What was my average speed yesterday?", "average"),
    ("Is there a pattern in the diagnostic logs?", "events"),
]


@pytest.mark.parametrize("question, expected", CASES)
def test_intent(question, expected):
    assert detect_intent(question) == expected


def test_columns():
    assert detect_column("why has driving range reduced") == "range_km"
    assert detect_column("fuel efficiency") == "energy_wh_per_km"
    assert detect_column("battery temperature") == "battery_temp"


def test_time_ranges():
    assert parse_time_range("show events from yesterday")[2] == "yesterday"
    assert parse_time_range("over the last two weeks")[2] == "the last 14 days"
    assert parse_time_range("anything")[0] is None
