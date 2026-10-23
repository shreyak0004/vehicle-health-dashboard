from api.chat_routes import chat_bp
from flask import Flask, jsonify, render_template, request

from vehicle_data import (
    generate_vehicle_data,
    check_vehicle_health,
    generate_recommendations
)

from genai.genai_testcases import generate_genai_testcases


app = Flask(__name__)
app.register_blueprint(chat_bp, url_prefix="/api")
# -----------------------------
# Trend buffers (history)
# -----------------------------
speed_history = []
battery_history = []
tyre_history = []
battery_temp_history = []
timestamps_history = []
MAX_HISTORY = 10


# -----------------------------
# Unified Cockpit Views
# -----------------------------
@app.route("/")
@app.route("/analytics")
@app.route("/alerts")
@app.route("/reports")
@app.route("/settings")
def home():
    return render_template("index.html")


# -----------------------------
# Main Vehicle Data Service
# -----------------------------
@app.route("/data")
def data():
    scenario = request.args.get("scenario", "normal")

    vehicle_data = generate_vehicle_data(scenario)
    alerts, health_score = check_vehicle_health(vehicle_data)
    recommendations = generate_recommendations(vehicle_data)

    # Update history buffers
    speed_history.append(vehicle_data["speed"])
    battery_history.append(vehicle_data["battery"])
    tyre_history.append(vehicle_data["tyre_pressure"])
    battery_temp_history.append(vehicle_data.get("battery_temp", 42.5))
    timestamps_history.append(vehicle_data["timestamp"])

    # Maintain fixed history size
    if len(speed_history) > MAX_HISTORY:
        speed_history.pop(0)

    if len(battery_history) > MAX_HISTORY:
        battery_history.pop(0)

    if len(tyre_history) > MAX_HISTORY:
        tyre_history.pop(0)

    if len(battery_temp_history) > MAX_HISTORY:
        battery_temp_history.pop(0)

    if len(timestamps_history) > MAX_HISTORY:
        timestamps_history.pop(0)

    return jsonify({
        "vehicle_data": vehicle_data,
        "alerts": alerts,
        "health_score": health_score,
        "recommendations": recommendations,
        "speed_history": speed_history,
        "battery_history": battery_history,
        "tyre_history": tyre_history,
        "battery_temp_history": battery_temp_history,
        "timestamps_history": timestamps_history,
        "scenario": scenario
    })


# -----------------------------
# Individual Vehicle Services (SoA)
# -----------------------------
@app.route("/service/speed")
def speed_service():
    scenario = request.args.get("scenario", "normal")
    vehicle_data = generate_vehicle_data(scenario)

    return jsonify({
        "service": "speed",
        "speed": vehicle_data["speed"],
        "timestamp": vehicle_data["timestamp"]
    })


@app.route("/service/battery")
def battery_service():
    scenario = request.args.get("scenario", "normal")
    vehicle_data = generate_vehicle_data(scenario)

    return jsonify({
        "service": "battery",
        "battery": vehicle_data["battery"],
        "timestamp": vehicle_data["timestamp"]
    })


@app.route("/service/health")
def health_service():
    scenario = request.args.get("scenario", "normal")
    vehicle_data = generate_vehicle_data(scenario)
    alerts, health_score = check_vehicle_health(vehicle_data)

    return jsonify({
        "service": "health",
        "health_score": health_score,
        "alerts": alerts,
        "timestamp": vehicle_data["timestamp"]
    })


# -----------------------------
# GenAI Test Case Generation Service
# -----------------------------
@app.route("/genai/testcases")
def genai_testcases():
    scenario = request.args.get("scenario", "normal")
    vehicle_data = generate_vehicle_data(scenario)

    genai_result = generate_genai_testcases(vehicle_data, scenario)

    return jsonify({
        "scenario": scenario,
        "vehicle_data": vehicle_data,
        "genai_analysis": genai_result
    })


# -----------------------------
# OTA & Service Registry
# -----------------------------
@app.route("/services")
def service_registry():
    return jsonify({
        "available_services": [
            {
                "name": "speed_service",
                "endpoint": "/service/speed",
                "description": "Provides real-time vehicle speed"
            },
            {
                "name": "battery_service",
                "endpoint": "/service/battery",
                "description": "Provides battery SoC information"
            },
            {
                "name": "health_service",
                "endpoint": "/service/health",
                "description": "Computes vehicle health score and alerts"
            },
            {
                "name": "genai_testcase_service",
                "endpoint": "/genai/testcases",
                "description": "AI-based diagnostics and validation insights"
            }
        ],
        "ota_note": "New services can be added or updated over-the-air without impacting existing services.",
        "vehicle_support": ["ICE", "Hybrid", "EV"]
    })


# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)