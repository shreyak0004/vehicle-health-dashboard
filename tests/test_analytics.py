import pytest
from database.db import init_db, get_connection
from analytics import queries as A

COLS = ("(vehicle_id, timestamp, speed, battery_temp, battery_soc, energy_wh_per_km,"
        " driving_mode, odometer_km, ambient_temp, range_km)")

# (vehicle, timestamp, speed, temp, soc, wh/km, mode, odo, ambient, range)
ROWS = [
    ("EV-001", "2025-01-01 08:00:00", 30, 35.0, 90, 130, "city",    100, 25, 300),
    ("EV-001", "2025-01-01 08:01:00", 100, 40.0, 89, 170, "highway", 101, 25, 298),
    ("EV-001", "2025-01-02 08:00:00", 30, 36.0, 90, 150, "city",    110, 25, 290),
    ("EV-001", "2025-01-02 08:01:00", 100, 41.0, 89, 190, "highway", 111, 25, 288),
    ("EV-001", "2025-01-03 08:00:00", 30, 37.0, 90, 200, "city",    120, 25, 250),
    ("EV-001", "2025-01-03 08:01:00", 100, 60.0, 89, 250, "highway", 121, 25, 248),
]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("VEHICLE_DB", str(tmp_path / "test.db"))
    init_db(reset=True)
    conn = get_connection()
    conn.executemany(f"INSERT INTO vehicle_readings {COLS} VALUES (?,?,?,?,?,?,?,?,?,?)", ROWS)
    conn.execute("INSERT INTO vehicle_events (vehicle_id, timestamp, event_type, severity, description) "
                 "VALUES ('EV-001','2025-01-03 08:01:00','BATTERY_OVERHEAT_WARNING','critical','test')")
    conn.commit()
    conn.close()


def test_highest_temperature(db):
    r = A.get_extreme("battery_temp", highest=True)
    assert r["value"] == 60.0
    assert r["timestamp"] == "2025-01-03 08:01:00"


def test_lowest_temperature(db):
    assert A.get_extreme("battery_temp", highest=False)["value"] == 35.0


def test_average_city(db):
    assert A.get_average("energy_wh_per_km", mode="city") == pytest.approx(160.0)


def test_compare_modes(db):
    r = A.compare_modes("energy_wh_per_km")
    assert r["city"] == pytest.approx(160.0)
    assert r["highway"] == pytest.approx(203.333, rel=1e-3)


def test_compare_city_vs_highway(db):
    res = A.compare_city_vs_highway()
    assert "speed" in res
    assert "energy_wh_per_km" in res
    assert "battery_temp" in res
    assert "battery_soc" in res
    assert res["speed"]["city"] == pytest.approx(30.0)
    assert res["speed"]["highway"] == pytest.approx(100.0)
    assert res["speed"]["diff"] == pytest.approx(70.0)
    assert res["energy_wh_per_km"]["city"] == pytest.approx(160.0)


def test_analyze_cold_weather_correlation(db):
    res = A.analyze_cold_weather_correlation()
    assert res is not None
    assert "what_changed" in res
    assert "when_changed" in res
    assert "readings" in res
    assert "observed_vs_explanation" in res
    assert len(res["readings"]) == 3



def test_daily_averages(db):
    days = A.daily_averages("energy_wh_per_km")
    assert [d["day"] for d in days] == ["2025-01-01", "2025-01-02", "2025-01-03"]
    assert days[0]["value"] == pytest.approx(150.0)


def test_largest_daily_increase(db):
    r = A.largest_daily_change("energy_wh_per_km", direction="increase")
    assert r["day"] == "2025-01-03"
    assert r["change"] == pytest.approx(55.0)


def test_trend(db):
    t = A.trend("energy_wh_per_km")
    assert t["first_half_avg"] == pytest.approx(150.0)
    assert t["second_half_avg"] == pytest.approx(197.5)


def test_events(db):
    ev = A.get_events("BATTERY_OVERHEAT_WARNING")
    assert len(ev) == 1


def test_readings_before_event(db):
    rows = A.get_readings_before_event("2025-01-03 08:01:00", minutes=5)
    assert len(rows) == 2
    assert rows[0]["battery_temp"] == 37.0


def test_anomalies(db):
    r = A.find_anomalies("battery_temp", z=2.0)
    # Only 6 rows: function needs >= 10, so we expect 0 here
    assert r["count"] == 0


def test_unknown_column_is_rejected(db):
    with pytest.raises(ValueError):
        A.get_extreme("drop_table; --")