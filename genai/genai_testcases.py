import random

def build_prompt(vehicle_data, scenario):
    """
    Builds a natural language prompt exactly like we would send to an LLM.
    """
    prompt = f"""
You are an automotive validation engineer.

Vehicle Scenario: {scenario}

Vehicle Parameters:
- Speed: {vehicle_data['speed']} km/h
- Battery: {vehicle_data['battery']} %
- Tyre Pressure: {vehicle_data['tyre_pressure']} PSI
- Gear: {vehicle_data['gear']}
- Throttle: {vehicle_data['throttle']} %
- Brake: {vehicle_data['brake']} %

Based on the above data:
1. Identify expected alerts
2. Estimate a health score range
3. Suggest driver recommendations
Return the result in structured form.
"""
    return prompt.strip()


def genai_reasoning_engine(vehicle_data, scenario):
    """
    Offline simulation of LLM reasoning.
    Output is NOT hardcoded by scenario,
    but derived from data conditions.
    """

    alerts = []
    recommendations = []
    health_score = 100

    # Reasoning based on data (not scenario name)
    if vehicle_data["battery"] < 20:
        alerts.append("Low Battery")
        health_score -= random.randint(20, 30)
        recommendations.append(
            "Reduce speed and enable regenerative braking to conserve battery."
        )

    if vehicle_data["speed"] > 100:
        alerts.append("Over Speeding")
        health_score -= random.randint(10, 20)
        recommendations.append(
            "Reduce speed to improve safety and energy efficiency."
        )

    if vehicle_data["tyre_pressure"] < 28:
        alerts.append("Low Tyre Pressure")
        health_score -= random.randint(10, 20)
        recommendations.append(
            "Inflate tyres to recommended pressure to avoid wear and instability."
        )

    if not alerts:
        recommendations.append(
            "Driving conditions are optimal. Maintain current driving behavior."
        )

    return {
        "expected_alerts": alerts,
        "expected_health_score_range": f"{max(health_score-10,0)}–{health_score}",
        "expected_recommendations": recommendations
    }


def generate_genai_testcases(vehicle_data, scenario):
    """
    Full GenAI pipeline:
    Prompt → Reasoning → Structured Output
    """
    prompt = build_prompt(vehicle_data, scenario)
    output = genai_reasoning_engine(vehicle_data, scenario)

    return {
        "prompt_used": prompt,
        "genai_output": output
    }
