import time

from flask import Blueprint, request, jsonify

from retrieval.query_engine import answer_question, evidence_text
from llm.local_model import generate_answer, model_available

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Please type a question."}), 400

    t0 = time.perf_counter()
    result = answer_question(question)               # exact facts (fast)
    t_retrieval = time.perf_counter() - t0
    facts = evidence_text(result)

    answer, used_llm = None, False
    safe_from_llm = result["intent"] in ["unsupported_signal", "control_refusal"]
    if result["intent"] != "unknown" and not safe_from_llm and model_available():
        try:
            answer = generate_answer(question, facts)
            used_llm = True
        except Exception as exc:                      # never crash the demo
            print("LLM error:", exc)
    if not answer or (result["intent"] == "compare" and not any(c.isdigit() for c in answer)):
        if result["facts"]:
            primary_fact = result["facts"][0]
            if result["intent"] == "compare":
                answer = " ".join(result["facts"])
            elif len(result["facts"]) > 1 and any(w in question.lower() for w in ["why", "cause", "explain", "before", "reduc", "drop", "change"]):
                answer = " ".join(result["facts"])
            elif safe_from_llm:
                answer = " ".join(result["facts"][:2])
            else:
                answer = primary_fact
        else:
            answer = "No diagnostic records matched the specified query."

    return jsonify({
        "answer": answer,
        "facts": result["facts"],
        "rows": result.get("rows", []),
        "chart": result["chart"],
        "intent": result["intent"],
        "used_llm": used_llm,
        "retrieval_seconds": round(t_retrieval, 3),
        "total_seconds": round(time.perf_counter() - t0, 3),
        "data_source": "simulated",
    })