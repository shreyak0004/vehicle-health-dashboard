from datetime import datetime
import random

def generate_vehicle_data(scenario="normal"):
    if scenario == "low_battery":
        speed = random.randint(20, 60)
        battery = random.randint(5, 15)
        tyre_pressure = random.randint(28, 34)
        battery_temp = round(random.uniform(35.0, 42.0), 1)

    elif scenario == "overspeed":
        speed = random.randint(100, 130)
        battery = random.randint(40, 80)
        tyre_pressure = random.randint(28, 34)
        battery_temp = round(random.uniform(49.0, 56.5), 1)

    else:  # normal
        speed = random.randint(30, 90)
        battery = random.randint(40, 100)
        tyre_pressure = random.randint(28, 36)
        battery_temp = round(random.uniform(37.0, 43.5), 1)

    return {
        "speed": speed,
        "battery": battery,
        "battery_temp": battery_temp,
        "tyre_pressure": tyre_pressure,

        # New vehicle signals
        "gear": random.choice(["P", "R", "N", "D"]),
        "throttle": random.randint(0, 100),   # %
        "brake": random.randint(0, 100),      # %

        "timestamp": datetime.now().strftime("%H:%M:%S")
    }




def check_vehicle_health(data):
    alerts = []
    score = 100

    # Battery logic
    if data["battery"] < 10:
        alerts.append("Critical Battery Level")
        score -= 40
    elif data["battery"] < 20:
        alerts.append("Low Battery")
        score -= 25

    # Tyre pressure logic
    if data["tyre_pressure"] < 28:
        alerts.append("Low Tyre Pressure")
        score -= 20

    # Speed logic
    if data["speed"] > 110:
        alerts.append("High Risk Over Speeding")
        score -= 25
    elif data["speed"] > 100:
        alerts.append("Over Speeding")
        score -= 15

    # Clamp score
    score = max(score, 0)

    return alerts, score
def generate_recommendations(data):
    recommendations = []

    if data["battery"] < 20:
        recommendations.append(
            "Reduce speed and enable regenerative braking to extend battery range."
        )

    if data["speed"] > 100:
        recommendations.append(
            "Reduce speed to avoid excessive energy consumption and component wear."
        )

    if data["tyre_pressure"] < 28:
        recommendations.append(
            "Inflate tyres to recommended pressure to improve safety and efficiency."
        )

    if not recommendations:
        recommendations.append(
            "Driving parameters are optimal. Maintain current driving style."
        )

    return recommendations

