
from retrieval.query_engine import answer_question, evidence_text

QUESTIONS = [
    "Why has driving range reduced over the last two weeks?",
    "When did fuel efficiency show the largest drop?",
    "Show ADAS disengagement events from yesterday",
    "What happened before the battery overheating warning?",
    "Compare energy consumption between city and highway driving",
    "What was the highest battery temperature yesterday?",
    "Were there any unusual temperature readings?",
]

for question in QUESTIONS:
    result = answer_question(question)

    print("\n" + "=" * 60)
    print("Q:", question)
    print("Intent:", result["intent"])
    print("Time range:", result["time_range"])
    print(evidence_text(result))
