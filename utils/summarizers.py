# ==Imports
from utils.json_utils import load_json
from paths import LONG_MEMORY_FILE

# ==Functions 
def summarize_recent_thoughts(n: int = 5) -> str:
    """
    Returns a short summary of the most recent reflections from long-term memory.
    """
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not long_memory:
        return "No recent thoughts found."

    recent = long_memory[-n:]
    summary_lines = [
        f"- {item['content']}" for item in recent if isinstance(item, dict) and 'content' in item
    ]

    return "\n".join(summary_lines) if summary_lines else "No recent thoughts with content."

def summarize_self_model(self_model: dict) -> dict:
    """
    Condenses the full self-model into a lightweight summary for prompting.
    """
    if not isinstance(self_model, dict):
        return {}

    return {
        "core_directive": self_model.get("core_directive", {}).get("statement", "Not found"),
        "core_values": self_model.get("core_values", []),
        "traits": self_model.get("personality_traits", []),
        "identity": self_model.get("identity_story", "An evolving reflective AI"),
        "known_roles": self_model.get("roles", []),
        "recent_focus": self_model.get("recent_focus", [])
    }