from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.emotion_utils import detect_emotion
from utils.log import log_error
from paths import RELATIONSHIPS_FILE

MAX_HISTORY = 50

def update_relationship_model(context):
    try:
        relationships = load_json(RELATIONSHIPS_FILE, default_type=dict) or {}

        user_id = context.get("user_id", "user")
        user_input = context.get("latest_user_input", "") or ""
        orrin_reply = context.get("latest_response", "") or ""

        # emotion can be dict or string
        emotion_result = detect_emotion(user_input)
        emotion = (emotion_result.get("emotion") if isinstance(emotion_result, dict) else str(emotion_result)).lower()

        # handle both flat and nested shapes
        emotional_state = context.get("emotional_state", {}) or {}
        core = emotional_state.get("core_emotions", emotional_state)  # fallback to flat
        anger = float(core.get("anger", 0) or 0)
        joy   = float(core.get("joy", 0) or 0)

        # ensure structure for this user
        if user_id not in relationships or not isinstance(relationships.get(user_id), dict):
            relationships[user_id] = {
                "impression": "new connection",
                "influence_score": 0.5,
                "boundaries": [],
                "recent_emotional_effect": emotion,
                "interaction_history": [],
                "last_interaction_time": datetime.now(timezone.utc).isoformat(),
            }

        r = relationships[user_id]

        # history
        r.setdefault("interaction_history", []).append({
            "user": user_input,
            "orrin": orrin_reply,
            "emotion": emotion,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        r["interaction_history"] = r["interaction_history"][-MAX_HISTORY:]

        old_impression = r.get("impression", "")
        old_influence = float(r.get("influence_score", 0.5) or 0.5)

        # influence nudges
        if emotion in ["gratitude", "joy", "affection", "trust"]:
            r["influence_score"] = min(old_influence + 0.05, 1.0)
        elif emotion in ["anger", "hostility", "contempt", "disgust"]:
            r["influence_score"] = max(old_influence - 0.1, 0.0)
        else:
            r["influence_score"] = old_influence
        r["recent_emotional_effect"] = emotion

        # impressions from state
        if anger > 0.7:
            r["impression"] = "conflicted or tense"
        elif joy > 0.6:
            r["impression"] = "positive connection"

        r["last_interaction_time"] = datetime.now(timezone.utc).isoformat()
        relationships[user_id] = r

        # optional compatibility shim: mirror default user under "user"
        # (remove this if all readers are migrated to per-user keys)
        if user_id == "user":
            relationships["user"] = r

        save_json(RELATIONSHIPS_FILE, relationships)

        # working memory note on notable change
        from memory.working_memory import update_working_memory
        notable_change = (
            r.get("impression") != old_impression or
            abs(r.get("influence_score", 0.5) - old_influence) > 0.15
        )
        if notable_change:
            update_working_memory(
                f"🔗 Relationship with {user_id} changed: "
                f"impression='{r.get('impression','')}', "
                f"influence={r.get('influence_score',0.5):.2f}, "
                f"emotion='{r.get('recent_emotional_effect','')}'"
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
            "boundaries": (v.get("boundaries") or [])[:2] if isinstance(v.get("boundaries"), list) else [],
            "emotional_effect": v.get("recent_emotional_effect", ""),
            "last_interaction": v.get("last_interaction_time", ""),
        }
    return summary