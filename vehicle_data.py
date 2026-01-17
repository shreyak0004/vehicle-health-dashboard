from datetime import datetime

import random

from datetime import datetime
import random

def generate_vehicle_data():
    return {
        "speed": random.randint(0, 120),
        "battery": random.randint(10, 100),
        "tyre_pressure": random.randint(24, 36),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }



def check_vehicle_health(data):
    alerts = []
    score = 100

    if data["battery"] < 20:
        alerts.append("Low Battery")
        score -= 30

    if data["tyre_pressure"] < 28:
        alerts.append("Low Tyre Pressure")
        score -= 30

    if data["speed"] > 100:
        alerts.append("Over Speeding")
        score -= 20

    if score < 0:
        score = 0

    return alerts, score
