from utils.coerce_to_string import coerce_to_string
from utils.load_utils import load_json
from paths import KNOWLEDGE

def recall_relevant_knowledge(context="", max_items=5):
    kb = load_json(KNOWLEDGE, default_type=list)
    if not isinstance(kb, list) or not context:
        return []

    context = coerce_to_string(context).lower()
    scored = []

    for entry in kb:
        if not isinstance(entry, dict):
            continue
        hits = sum(
            isinstance(term, str) and term.lower() in context
            for term in entry.get("relevance", [])
        )
        if hits > 0:
            confidence = entry.get("confidence", 0.5)
            scored.append((hits + confidence, entry))

    sorted_entries = sorted(scored, key=lambda x: -x[0])
    return [entry["summary"] for _, entry in sorted_entries[:max_items] if "summary" in entry]


