# from flask import Flask, jsonify, render_template
# from vehicle_data import generate_vehicle_data, check_vehicle_health

# import random

# app = Flask(__name__)

# # -----------------------------
# # Vehicle Data Simulation
# # -----------------------------
# def generate_vehicle_data():
#     return {
#         "speed": random.randint(0, 120),
#         "battery": random.randint(10, 100),
#         "tyre_pressure": random.randint(24, 36)
#     }

# # -----------------------------
# # Vehicle Health Logic
# # -----------------------------
# def check_vehicle_health(vehicle_data):
#     alerts = []
#     score = 100

#     if vehicle_data["battery"] < 20:
#         alerts.append("Low Battery")
#         score -= 30

#     if vehicle_data["tyre_pressure"] < 28:
#         alerts.append("Low Tyre Pressure")
#         score -= 30

#     if vehicle_data["speed"] > 100:
#         alerts.append("Over Speeding")
#         score -= 20

#     if score < 0:
#         score = 0

#     return alerts, score

# # -----------------------------
# # Routes
# # -----------------------------
# @app.route("/")
# def home():
#     return render_template("index.html")

# @app.route("/data")
# def data():
#     vehicle_data = generate_vehicle_data()
#     alerts, health_score = check_vehicle_health(vehicle_data)

#     return jsonify({
#         "vehicle_data": vehicle_data,
#         "alerts": alerts,
#         "health_score": health_score
#     })

# # -----------------------------
# if __name__ == "__main__":
#     app.run(debug=True)

from flask import Flask, jsonify, render_template
from vehicle_data import generate_vehicle_data, check_vehicle_health

app = Flask(__name__)

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    vehicle_data = generate_vehicle_data()
    alerts, health_score = check_vehicle_health(vehicle_data)

    return jsonify({
        "vehicle_data": vehicle_data,
        "alerts": alerts,
        "health_score": health_score
    })

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
