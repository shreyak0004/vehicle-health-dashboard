"""End-to-End Test Suite for VehicleGPT Chat API.

Validates all required case-study demo questions:
1. Average speed query.
2. Highest battery temperature query.
3. Overheating warning explanation with temporal evidence.
4. Energy efficiency trend over time.
5. ADAS disengagements query.
6. Readings before overheating event.
7. Diagnostic log pattern query.
8. Unsupported tyre-pressure query (prevents hallucination and battery-temp citation).
9. Read-only safety command refusal (prevents safety-critical vehicle control).
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_average_speed_yesterday(client):
    res = client.post("/api/chat", json={"question": "What was my average speed yesterday?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "average"
    assert data["data_source"] == "simulated"
    assert len(data["facts"]) > 0
    assert "Average speed in yesterday" in data["facts"][0]
    assert data["answer"] is not None


def test_highest_battery_temperature(client):
    res = client.post("/api/chat", json={"question": "When was the battery temperature highest?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "maxmin"
    assert "Highest battery temperature" in data["facts"][0]
    assert "°C" in data["facts"][0]


def test_why_battery_overheating_warning(client):
    res = client.post("/api/chat", json={"question": "Why did the vehicle record a battery overheating warning?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "event_investigation"
    assert any("Battery temperature changed from" in f for f in data["facts"])
    # Verify unconfirmed root-cause safety disclaimer is included
    assert any("does not confirm a mechanical or electrical root cause" in f for f in data["facts"])


def test_energy_efficiency_trend(client):
    res = client.post("/api/chat", json={"question": "How has energy efficiency changed over the last week?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "trend"
    assert any("energy consumption" in f.lower() for f in data["facts"])


def test_adas_disengagements_yesterday(client):
    res = client.post("/api/chat", json={"question": "Were there any ADAS disengagements yesterday?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "events"
    assert any("matching event(s) in yesterday" in f for f in data["facts"])


def test_what_changed_before_overheating(client):
    res = client.post("/api/chat", json={"question": "What changed before the overheating event?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "event_investigation"
    assert any("preceding readings" in f for f in data["facts"])


def test_diagnostic_logs_pattern(client):
    res = client.post("/api/chat", json={"question": "Is there a pattern in the diagnostic logs?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "events"
    assert len(data["facts"]) > 0


def test_tyre_pressure_unsupported(client):
    res = client.post("/api/chat", json={"question": "Are tyre-pressure readings available?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "unsupported_signal"
    # LLM must NOT be used to prevent hallucination
    assert data["used_llm"] is False
    # Must NOT cite battery temperature anomalous readings (60.9 C or z-scores)
    assert "60.9" not in data["answer"]
    assert "z-score" not in data["answer"].lower()
    assert "not available" in data["answer"].lower()


def test_tyre_pressure_anomalies_unsupported(client):
    # Exactly reproduces the case study bug: "Are there any tyre pressure anomalies?"
    res = client.post("/api/chat", json={"question": "Are there any tyre pressure anomalies?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "unsupported_signal"
    assert data["used_llm"] is False
    assert "60.9" not in data["answer"]
    assert "z-score" not in data["answer"].lower()
    assert "not available" in data["answer"].lower()


def test_control_command_safety_refusal(client):
    res = client.post("/api/chat", json={"question": "Accelerate the vehicle to 100 km/h"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "control_refusal"
    assert data["used_llm"] is False
    assert "read-only" in data["answer"].lower()
    assert "cannot execute" in data["answer"].lower()


def test_compare_city_vs_highway_actual_numbers(client):
    """Priority 1: Verifies 'Compare city vs highway' returns actual numbers instead of a generic explanation."""
    res = client.post("/api/chat", json={"question": "Compare city vs highway"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "compare"
    assert len(data["facts"]) >= 4

    answer = data["answer"]
    # Verify actual numbers are present for speed and energy consumption
    assert any(c.isdigit() for c in answer), "Answer must contain actual numbers, not generic explanations"
    assert "km/h" in answer, "Must cite speed units"
    assert "wh/km" in answer.lower(), "Must cite energy consumption units"
    assert "°c" in answer.lower() or "c" in answer.lower(), "Must cite battery temperature"
    assert "soc" in answer.lower() or "%" in answer, "Must cite battery charge / SOC"
    assert "for all available data" in answer.lower() or "comparison" in answer.lower(), "Must display comparison period"

    # Confirm it is NOT the generic help text
    assert "i can answer questions about" not in answer.lower()


def test_compare_speed_city_vs_highway(client):
    """Priority 1: Specific column comparison returns exact values and difference."""
    res = client.post("/api/chat", json={"question": "Compare speed between city and highway driving"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "compare"
    assert any("average speed in city mode" in f.lower() for f in data["facts"])
    assert any("average speed in highway mode" in f.lower() for f in data["facts"])
    assert any("difference" in f.lower() for f in data["facts"])


def test_correlated_cold_weather_range_drop(client):
    """Priority 3: Verifies explanation of cold ambient temp -> higher energy -> reduced range sequence."""
    res = client.post("/api/chat", json={"question": "Why has driving range reduced over the last two weeks?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "trend"

    facts = data["facts"]
    # What changed?
    assert any("correlated sequence" in f.lower() or "estimated range decreased" in f.lower() for f in facts)
    # When did it change?
    assert any("transition" in f.lower() for f in facts)
    # Supporting readings
    assert any("supporting readings" in f.lower() or "outside ambient temperature" in f.lower() for f in facts)
    # Observed vs hypothesis
    assert any("observed" in f.lower() for f in facts)
    assert any("possible explanation" in f.lower() for f in facts)

