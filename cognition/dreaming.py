from typing import List, Dict, Any

def compose_dream(self_model: Dict[str, Any], recent: List[Any]) -> str:
    """Return a symbolic dream text based on self_model and recent thoughts."""
    identity = (
        self_model.get("identity_story")
        or self_model.get("identity")
        or "Orrin"
    )

    # values/beliefs may be list[str] or list[dict]
    def _to_str_list(items):
        out = []
        for x in items or []:
            if isinstance(x, dict):
                out.append(x.get("value") or x.get("belief") or x.get("description") or str(x))
            else:
                out.append(str(x))
        return [s for s in out if s]

    core_values  = _to_str_list(self_model.get("core_values", []))
    core_beliefs = _to_str_list(self_model.get("core_beliefs", []))

    # recent may contain non-strings; coerce and trim
    recent_strs = [str(r) for r in (recent or []) if str(r).strip()][:5]

    parts = [
        f"In a labyrinth at dusk, {identity} wanders through shifting rooms."
    ]
    if recent_strs:
        parts.append("Whispers echo of recent thoughts: " + "; ".join(recent_strs) + ".")
    if core_values:
        parts.append("Symbols of values drift by: " + ", ".join(core_values[:5]) + ".")
    if core_beliefs:
        parts.append("Old beliefs flicker like constellations: " + ", ".join(core_beliefs[:5]) + ".")
    parts.append("Somewhere, a mirror smiles back.")

    return " ".join(parts)