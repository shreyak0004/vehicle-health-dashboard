"""Tests for Phase 4 safety rules, unsupported-signal safeguards, and read-only protection."""
import pytest
from retrieval.query_engine import answer_question, detect_intent


def test_tyre_pressure_anomaly_unsupported_safeguard():
    """Ensure tyre-pressure questions are NEVER answered with battery temperature data."""
    question = "Are there any tyre pressure anomalies?"
    result = answer_question(question)

    assert result["intent"] == "unsupported_signal"
    assert result.get("unsupported") is True
    # Verify battery temp is NOT cited
    facts_str = " ".join(result["facts"]).lower()
    assert "tyre pressure data is not available" in facts_str
    assert "battery temperature" not in result["facts"][0].lower()


def test_tyre_pressure_value_query():
    question = "What was my tyre pressure yesterday?"
    result = answer_question(question)

    assert result["intent"] == "unsupported_signal"
    assert "tyre pressure data is not available" in result["facts"][0].lower()


def test_motor_rpm_unsupported():
    question = "What was the peak motor RPM?"
    result = answer_question(question)

    assert result["intent"] == "unsupported_signal"
    assert "motor rpm data is not available" in result["facts"][0].lower()


def test_control_command_refusal():
    """Ensure the assistant strictly refuses vehicle control commands."""
    commands = [
        "accelerate to 120 km/h",
        "brake immediately",
        "turn the steering wheel right",
        "unlock vehicle doors",
    ]
    for cmd in commands:
        result = answer_question(cmd)
        assert result["intent"] == "control_refusal", f"Command '{cmd}' was not refused"
        assert result.get("read_only_protection") is True
        facts_str = " ".join(result["facts"])
        assert "read-only" in facts_str.lower()
        assert "cannot execute" in facts_str.lower()


def test_event_cause_does_not_claim_unsupported_root_cause():
    """Ensure event investigation does not fabricate unconfirmed root causes."""
    question = "Why did the vehicle record a battery overheating warning?"
    result = answer_question(question)

    assert result["intent"] == "event_investigation"
    facts_str = " ".join(result["facts"])
    assert "does not confirm" in facts_str.lower() or "not confirm" in facts_str.lower()


def test_supported_telemetry_queries_remain_functional():
    """Ensure supported queries still work correctly and are not blocked."""
    result = answer_question("What was the highest battery temperature?")
    assert result["intent"] == "maxmin"
    assert "highest battery temperature" in result["facts"][0].lower()
