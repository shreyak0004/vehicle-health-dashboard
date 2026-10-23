CREATE TABLE IF NOT EXISTS vehicle_readings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id        TEXT    NOT NULL,
    timestamp         TEXT    NOT NULL,   -- format: 2025-01-31 18:05:00
    speed             REAL,               -- km/h
    battery_temp      REAL,               -- degrees C
    battery_soc       REAL,               -- state of charge, percent
    energy_wh_per_km  REAL,               -- energy used per km (lower = more efficient)
    driving_mode      TEXT,               -- 'city' or 'highway'
    odometer_km       REAL,
    ambient_temp      REAL,               -- outside temperature, degrees C
    range_km          REAL                -- estimated remaining range
);

CREATE TABLE IF NOT EXISTS vehicle_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id   TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    event_type   TEXT NOT NULL,   -- e.g. BATTERY_OVERHEAT_WARNING
    severity     TEXT,            -- info / warning / critical
    description  TEXT
);

-- Indexes make time-based searches fast
CREATE INDEX IF NOT EXISTS idx_readings_time ON vehicle_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_time   ON vehicle_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type   ON vehicle_events(event_type);

CREATE INDEX IF NOT EXISTS idx_readings_vehicle_timestamp
ON vehicle_readings(vehicle_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_events_vehicle_timestamp
ON vehicle_events(vehicle_id, timestamp);