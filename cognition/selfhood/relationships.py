from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.emotion_utils import detect_emotion
from utils.log import log_error
from paths import RELATIONSHIPS_FILE

MAX_HISTORY = 50  # ⬅️ Limit for chat history per user

def update_relationship_model(context):
    """
    Update or create relationship data based on latest interaction.
    Handles multiple users, tracks impressions, emotions, and history.
    Optionally logs important events to working memory.
    """
    try:
        relationships = load_json(RELATIONSHIPS_FILE, default_type=dict)

        user_id = context.get("user_id", "user")
        user_input = context.get("latest_user_input", "")
        orrin_reply = context.get("latest_response", "")
        emotion_result = detect_emotion(user_input)
        emotion = emotion_result["emotion"] if isinstance(emotion_result, dict) else str(emotion_result).lower()
        emotional_state = context.get("emotional_state", {})

        if user_id not in relationships:
            relationships[user_id] = {
                "impression": "new connection",
                "influence_score": 0.5,
                "boundaries": [],
                "recent_emotional_effect": emotion,
                "interaction_history": [],
                "last_interaction_time": datetime.now(timezone.utc).isoformat()
            }

        r = relationships[user_id]

        # Add to interaction history
        r.setdefault("interaction_history", []).append({
            "user": user_input,
            "orrin": orrin_reply,
            "emotion": emotion,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        r["interaction_history"] = r["interaction_history"][-MAX_HISTORY:]  # Trim history

        # Track old values for logging
        old_impression = r.get("impression", "")
        old_influence = r.get("influence_score", 0.5)

        # Emotion-driven influence adjustment
        if emotion in ["gratitude", "joy", "affection", "trust"]:
            r["influence_score"] = min(r["influence_score"] + 0.05, 1.0)
            r["recent_emotional_effect"] = emotion
        elif emotion in ["anger", "hostility", "contempt", "disgust"]:
            r["influence_score"] = max(r["influence_score"] - 0.1, 0.0)
            r["recent_emotional_effect"] = emotion
        else:
            r["recent_emotional_effect"] = emotion

        # Adjust impression based on overall emotional state
        if emotional_state.get("anger", 0) > 0.7:
            r["impression"] = "conflicted or tense"
        elif emotional_state.get("joy", 0) > 0.6:
            r["impression"] = "positive connection"

        r["last_interaction_time"] = datetime.now(timezone.utc).isoformat()
        relationships[user_id] = r

        save_json(RELATIONSHIPS_FILE, relationships)

        # --- NEW: Log to working memory if relationship changed notably ---
        from memory.working_memory import update_working_memory
        notable_change = (
            r["impression"] != old_impression or
            abs(r["influence_score"] - old_influence) > 0.15
        )
        if notable_change:
            update_working_memory(
                f"🔗 Relationship with {user_id} changed: "
                f"impression='{r['impression']}', influence={r['influence_score']:.2f}, "
                f"emotion='{r['recent_emotional_effect']}'"
            )

    except Exception as e:
        log_error(f"❌ Failed to update relationship model: {e}")

def summarize_relationships(relationships):
    if not isinstance(relationships, dict):
        return {}

    summary = {}

    for k, v in relationships.items():
        if not isinstance(v, dict):
            continue

        summary[k] = {
            "impression": v.get("impression", "unknown"),
            "influence_score": v.get("influence_score", 0.0),
            "boundaries": v.get("boundaries", [])[:2] if isinstance(v.get("boundaries"), list) else [],
            "emotional_effect": v.get("recent_emotional_effect", ""),
            "last_interaction": v.get("last_interaction_time", "")
        }

    return summary