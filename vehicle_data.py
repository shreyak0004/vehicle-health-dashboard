import random
import time

def generate_vehicle_data():
    return {
        "speed": random.randint(0, 120),          # km/h
        "battery": random.randint(10, 100),       # %
        "tyre_pressure": random.randint(24, 36)   # PSI
    }

def check_vehicle_health(data):
    alerts = []

    if data["battery"] < 20:
        alerts.append("Low Battery")

    if data["tyre_pressure"] < 28:
        alerts.append("Low Tyre Pressure")

    if data["speed"] > 100:
        alerts.append("Over Speeding")

    return alerts

while True:
    vehicle_data = generate_vehicle_data()
    alerts = check_vehicle_health(vehicle_data)

    print("Vehicle Data:", vehicle_data)

    if alerts:
        print("ALERTS:", alerts)
    else:
        print("Status: Vehicle is healthy")

    print("-" * 40)
    time.sleep(2)
