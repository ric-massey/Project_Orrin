def summarize_relationships(relationships):
    if not isinstance(relationships, dict):
        return {}

    summary = {}

    for k, v in relationships.items():
        if not isinstance(v, dict):
            continue  # skip malformed entries

        summary[k] = {
            "impression": v.get("impression", "unknown"),
            "influence_score": v.get("influence_score", 0.0),
            "boundaries": v.get("boundaries", [])[:2] if isinstance(v.get("boundaries"), list) else [],
            "emotional_effect": v.get("recent_emotional_effect", "")
        }

    return summary