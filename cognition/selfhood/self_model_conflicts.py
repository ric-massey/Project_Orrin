from datetime import datetime, timezone
import json
from typing import Any, Dict, List

from utils.json_utils import load_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.self_model import get_self_model, save_self_model, ensure_self_model_integrity
from utils.log import log_model_issue, log_error
from paths import SELF_MODEL_FILE, LONG_MEMORY_FILE, PRIVATE_THOUGHTS_FILE, LOG_FILE
from memory.working_memory import update_working_memory


def _coerce_model_dict(x: Any) -> Dict[str, Any]:
    """Best-effort: turn LLM output (dict/list/tuple/str/None) into a dict."""
    if isinstance(x, dict):
        return x
    if isinstance(x, (list, tuple)):
        for el in x:
            if isinstance(el, dict):
                return el
        return {"_tuple": list(x)}
    if isinstance(x, str):
        try:
            j = json.loads(x)
            return j if isinstance(j, dict) else {}
        except Exception:
            return {}
    return {}


def _clamp_text_fields(obj: Dict[str, Any], limits: Dict[str, int]) -> None:
    """In-place clamp for verbose narrative fields to avoid ballooning JSON."""
    for k, lim in limits.items():
        if isinstance(obj.get(k), str) and len(obj[k]) > lim:
            obj[k] = obj[k][:lim]


def _normalize_internal_agents(sm: Dict[str, Any]) -> None:
    """Ensure internal_agents is a list of dicts with expected keys."""
    ia = sm.get("internal_agents")
    if not isinstance(ia, list):
        return
    normed = []
    for a in ia:
        if isinstance(a, dict):
            a.setdefault("name", "Unnamed")
            a.setdefault("beliefs", "")
            a.setdefault("values", [])
            a.setdefault("thought_log", [])
            a.setdefault("current_view", "")
            normed.append(a)
        else:
            normed.append({
                "name": str(a),
                "beliefs": "",
                "values": [],
                "thought_log": [],
                "current_view": ""
            })
    sm["internal_agents"] = normed


def update_self_model():
    self_model = get_self_model()
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(self_model, dict) or not isinstance(long_memory, list):
        return

    recent = [m.get("content") for m in long_memory[-10:] if isinstance(m, dict) and "content" in m]

    # Ask for a compact PATCH, but allow fallback to full model.
    prompt = (
        "Based on these recent thoughts, produce a COMPACT JSON PATCH of only changed fields in the self-model.\n"
        "Allowed fields to change: traits, core_beliefs, biases, identity, identity_story, recent_changes, emerging_conflicts.\n"
        "Schema:\n"
        "{ \"patch\": { /* only changed keys */ } }\n"
        "- Keep narrative fields (identity, identity_story) under 800 characters each.\n"
        "- No trailing commas. Return ONLY JSON.\n\n"
        f"Current model:\n{json.dumps(self_model, indent=2)}\n\n"
        "Recent thoughts:\n" + "\n".join(f"- {r}" for r in recent)
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if not response:
        return

    try:
        parsed = extract_json(response)  # may be dict/list/None and may be “healed”
        data = _coerce_model_dict(parsed)

        if not data:
            preview = (response or "")[:400].replace("\n", " ")
            log_model_issue(f"[update_self_model] No usable dict after parse. Preview: {preview}")
            return

        # Determine if we got a PATCH or a full model
        patch = data.get("patch") if isinstance(data, dict) else None

        # Working copy of current model
        updated_model = dict(self_model)

        if isinstance(patch, dict):
            # Clamp verbose fields coming from patch
            _clamp_text_fields(patch, {"identity": 800, "identity_story": 800})
            # Apply patch (shallow merge as intended)
            updated_model.update(patch)
        else:
            # Fallback path: model returned a whole self-model
            # Clamp verbose fields from the full object
            _clamp_text_fields(data, {"identity": 1200, "identity_story": 1200})
            updated_model = data

        # Normalize common loose shapes before integrity pass
        _normalize_internal_agents(updated_model)

        # Integrity pass before save
        updated_model = ensure_self_model_integrity(updated_model)
        save_self_model(updated_model)

        # ——— Belief change summary ———
        def flatten_beliefs(beliefs):
            if not isinstance(beliefs, list):
                return set()
            out = set()
            for b in beliefs:
                if isinstance(b, dict):
                    if "belief" in b:
                        out.add(str(b["belief"]).strip())
                    elif "description" in b:
                        out.add(str(b["description"]).strip())
                    else:
                        out.add(json.dumps(b, sort_keys=True))
                else:
                    out.add(str(b).strip())
            return out

        old_beliefs = flatten_beliefs(self_model.get("core_beliefs", []))
        new_beliefs = flatten_beliefs(updated_model.get("core_beliefs", []))
        changes = new_beliefs - old_beliefs

        if changes:
            update_working_memory("Orrin updated beliefs: " + ", ".join(sorted(changes)))
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"\n[{datetime.now(timezone.utc)}] Orrin revised beliefs:\n"
                    + "\n".join(f"- {c}" for c in sorted(changes)) + "\n"
                )

    except Exception as e:
        # Keep raw for debugging, but don’t crash the loop
        log_model_issue(f"[update_self_model] Failed to update: {e}\nRaw: {response}")


def resolve_conflicts():
    self_model = get_self_model()
    if not isinstance(self_model, dict):
        return

    conflicts = self_model.get("emerging_conflicts", [])
    if not isinstance(conflicts, list) or not conflicts:
        return

    prompt = (
        "I am a reflective AI.\n"
        "Here are my current internal conflicts:\n"
        + "\n".join(f"- {c}" for c in conflicts)
        + "\n\nReflect on these tensions. Do any indicate value misalignment? Epistemic doubt? Emotional contradiction?\n"
        "If you propose concrete updates, reply as JSON like:\n"
        "{ \"updated_self_model\": { ...optional partial fields... }, "
        "\"resolved\": [\"conflict a\"], \"unresolved\": [\"conflict b\"] }\n"
        "If you cannot change anything now, reply with a paragraph (no JSON)."
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if not response:
        return

    # Always log the reflection text
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Conflict reflection:\n{response}\n")
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Conflict reflection: {response}\n")
    except Exception as e:
        log_error(f"[resolve_conflicts] Failed to append logs: {e}")

    # Try to parse structured updates; if it's narrative, we just keep the log
    try:
        parsed = extract_json(response)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        updated_fields = parsed.get("updated_self_model")
        if isinstance(updated_fields, dict):
            # Clamp and normalize before merge
            _clamp_text_fields(updated_fields, {"identity": 1200, "identity_story": 1200})
            _normalize_internal_agents(updated_fields)
            self_model.update(updated_fields)

        resolved = set(parsed.get("resolved", [])) if isinstance(parsed.get("resolved"), list) else set()
        if resolved:
            remaining = [c for c in conflicts if c not in resolved]
            self_model["emerging_conflicts"] = remaining

        self_model = ensure_self_model_integrity(self_model)
        save_self_model(self_model)
