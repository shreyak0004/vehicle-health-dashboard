
from database.db import get_readonly_connection

with get_readonly_connection() as conn:
    readings = conn.execute(
        "SELECT COUNT(*) AS total FROM vehicle_readings"
    ).fetchone()["total"]

    events = conn.execute(
        "SELECT event_type, COUNT(*) AS total "
        "FROM vehicle_events GROUP BY event_type"
    ).fetchall()

    yesterday_adas = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM vehicle_events
        WHERE event_type = 'ADAS_DISENGAGEMENT'
          AND date(timestamp) = date('now', 'localtime', '-1 day')
        """
    ).fetchone()["total"]

    print("Total readings:", readings)
    print("Event counts:")
    for event in events:
        print(f"  {event['event_type']}: {event['total']}")
    print("ADAS events yesterday:", yesterday_adas)
