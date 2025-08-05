import json
from utils.log import log_error
from paths import REFLECTION

def extract_last_reflection_topic(context=None, reflection_log_path=REFLECTION):
    try:
        # 1. Prefer emotionally tagged working memory entries
        if context and "working_memory" in context:
            wm = context["working_memory"]
            for entry in reversed(wm[-30:]):
                if entry.get("type") in {"emotion", "self_belief_reflection", "reflection"}:
                    content = entry.get("content", "").strip()
                    if content:
                        return clean_snippet(content)

        # 2. Fallback to reflection log file
        with open(reflection_log_path, "r", encoding="utf-8") as f:
            reflections = json.load(f)
        for entry in reversed(reflections):
            if entry.get("type", "").lower() in {"reflection", "self_belief", "belief"}:
                content = entry.get("content", "").strip()
                if content:
                    return clean_snippet(content)

        # 3. Last-ditch: Use recent emotion or value
        if context and "emotional_state" in context:
            top_emotion = context["emotional_state"].get("top_emotion", "curiosity")
            return f"emotional reflection on {top_emotion}"

        return "ambiguous_reflection_trigger"
    except Exception as e:
        log_error(f"[extract_last_reflection_topic] ERROR: {e}")
        return "reflection_topic_unknown"

def clean_snippet(text):
    snippet = text[:60].rsplit(' ', 1)[0]
    return snippet if snippet else text[:60]