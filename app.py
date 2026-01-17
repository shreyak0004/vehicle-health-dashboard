from flask import Flask, jsonify, render_template

import random

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    vehicle_data = {
        "speed": random.randint(0, 120),
        "battery": random.randint(10, 100),
        "tyre_pressure": random.randint(24, 36)
    }

    alerts = []
    if vehicle_data["battery"] < 20:
        alerts.append("Low Battery")
    if vehicle_data["tyre_pressure"] < 28:
        alerts.append("Low Tyre Pressure")
    if vehicle_data["speed"] > 100:
        alerts.append("Over Speeding")

    return jsonify({
        "vehicle_data": vehicle_data,
        "alerts": alerts
    })

if __name__ == "__main__":
    app.run(debug=True)
