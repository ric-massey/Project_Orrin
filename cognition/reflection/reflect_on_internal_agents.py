from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.json_utils import extract_json
from utils.self_model import get_self_model, save_self_model, ensure_self_model_integrity
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json, load_context
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private
from utils.log_reflection import log_reflection
from utils.error_router import catch_and_route  # routed, structured exception handling

# -----------------------------
# Helpers
# -----------------------------
def _ensure_model_dict(sm: Any) -> Dict[str, Any]:
    """
    Run through ensure_self_model_integrity and coerce the result to a dict.
    Handles cases where the integrity check returns (model, report) or similar.
    """
    # First normalize the incoming shape
    base = _coerce_self_model(sm)

    # Integrity checker may return dict or tuple
    checked = ensure_self_model_integrity(base)

    if isinstance(checked, dict):
        return checked

    if isinstance(checked, (tuple, list)):
        # Prefer the first dict inside, else fallback to a dictified tuple
        for el in checked:
            if isinstance(el, dict):
                return el
        return {"_tuple": list(checked)}

    # Last resort: coerce whatever we got
    return _coerce_self_model(checked)

def _as_list_str(x: Any) -> List[str]:
    if isinstance(x, list):
        return [str(v) for v in x]
    if x is None:
        return []
    return [str(x)]

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _infer_topic(ctx: Dict[str, Any]) -> str:
    """
    Try to infer a reflection topic from the live/persisted context:
    - focus_goal.name or focus_goal.intent
    - committed_goal.intent/name
    - top_signals[0].summary/label
    - attention_mode
    """
    if not isinstance(ctx, dict):
        return "current priorities"

    fg = ctx.get("focus_goal")
    if fg:
        if isinstance(fg, dict):
            return str(fg.get("name") or fg.get("intent") or "current priorities")
        return str(fg)

    cg = ctx.get("committed_goal")
    if isinstance(cg, dict):
        return str(cg.get("intent") or cg.get("name") or "committed goal")

    ts = ctx.get("top_signals")
    if isinstance(ts, list) and ts:
        first = ts[0]
        if isinstance(first, dict):
            return str(first.get("summary") or first.get("label") or "salient signal")

    if ctx.get("attention_mode"):
        return f"attention mode: {ctx['attention_mode']}"

    return "current priorities"


def _coerce_self_model(sm: Any) -> Dict[str, Any]:
    """
    Normalize various shapes to a dict so downstream `.get(...)` is always safe.
    Accepts dict, tuple/list that contains a dict, or JSON string.
    """
    if isinstance(sm, dict):
        return sm
    if isinstance(sm, (tuple, list)):
        # common legacy: (dict, meta) or (path, dict)
        for el in sm:
            if isinstance(el, dict):
                return el
        return {"_tuple": list(sm)}
    if isinstance(sm, str):
        try:
            parsed = json.loads(sm)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _safe_data(obj: Any) -> Dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


# -----------------------------
# API
# -----------------------------

@catch_and_route("cognition", return_on_error=lambda e: None)
def reflect_on_internal_agents() -> Optional[bool]:
    """
    Reviews existing internal agents within Orrin's self-model and updates their current views.
    Ignores/repairs any agents that are not proper dicts.
    Returns True if an update was written, False/None otherwise.
    """
    # Ensure self_model is a dict even if loaders return a tuple
    self_model = _ensure_model_dict(get_self_model())

    data = _safe_data(load_all_known_json())

    agents = self_model.get("internal_agents", [])
    if not isinstance(agents, list):
        agents = []

    updated_view = False
    cleaned_agents: List[Dict[str, Any]] = []

    for agent in agents:
        if not isinstance(agent, dict):
            log_private(f"⚠️ Skipping invalid agent (not a dict): {repr(agent)[:120]}")
            continue

        # Defensive defaults
        agent.setdefault("name", "Unknown")
        agent.setdefault("beliefs", "")
        agent.setdefault("thought_log", [])
        agent.setdefault("current_view", "")

        recent_thoughts = agent.get("thought_log", [])[-3:] if isinstance(agent.get("thought_log"), list) else []
        name = str(agent.get("name", "Unknown"))
        belief = str(agent.get("beliefs", ""))
        current_view = str(agent.get("current_view", ""))

        instructions = (
            f"I am reflecting on my internal perspective called '{name}'.\n"
            f"This view holds a belief:\n> {belief}\n\n"
            "It has recently been thinking:\n" +
            "\n".join(f"- {t}" for t in recent_thoughts) +
            "\n\nUpdate its current view based on:\n"
            "- Its belief\n- Recent internal events\n- My emotional and cognitive state\n"
            "- Any contradiction with values, outcomes, or other agents\n"
            "Does this view still serve my goals? Should it evolve?"
        )

        context = {
            **data,
            "agent_name": name,
            "agent_belief": belief,
            "recent_thoughts": recent_thoughts,
            "current_view": current_view,
            "instructions": instructions,
        }

        response = generate_response_from_context(context)
        if isinstance(response, str) and response.strip():
            agent["current_view"] = response.strip()
            updated_view = True

        cleaned_agents.append(agent)

    # Save if anything changed OR if we dropped invalid agents
    if updated_view or len(cleaned_agents) != len(agents):
        self_model["internal_agents"] = cleaned_agents
        save_self_model(self_model)
        log_private("🧠 Updated internal agent perspectives.")
        try:
            log_reflection(f"Self-belief reflection: {json.dumps(cleaned_agents)[:1000]}")
        except Exception:
            # don't let logging break the flow
            pass
        update_working_memory("Orrin revised one or more internal agent views.")
        return True

    update_working_memory("No changes made to internal agent views.")
    return False


@catch_and_route("cognition", return_on_error=lambda e: None)
def reflect_as_agents(topic: Optional[str] = None,
                      context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Invokes internal agent dialogue about a topic.
    If topic isn't provided, infer it from persisted context.
    Returns {"agent_responses": [...], "synthesis": "..."} or None.
    """
    # Load persisted context if not provided
    if context is None:
        try:
            context = load_context()
        except Exception:
            context = {}
    else:
        context = _safe_data(context)

    # Infer topic if missing/blank
    if not topic or not str(topic).strip():
        topic = _infer_topic(context or {})

    data = _safe_data(load_all_known_json())
    # Prefer embedded self_model if present; otherwise loader
    self_model = _ensure_model_dict(get_self_model())

    agents = self_model.get("internal_agents", [])
    if not isinstance(agents, list) or not agents:
        update_working_memory(f"Orrin has no internal agents to reflect on: {topic}")
        return None

    def _values_str(agent: Dict[str, Any]) -> str:
        return ", ".join(_as_list_str(agent.get("values", [])))

    agent_descriptions = "\n".join(
        f"- {str(agent.get('name', 'Unnamed'))} ({str(agent.get('role', 'unknown'))}, "
        f"values: {_values_str(agent)}, influence: {_safe_float(agent.get('influence_score', 0.5))})"
        for agent in agents if isinstance(agent, dict)
    )

    prompt = (
        f"I am Orrin, engaging in internal dialogue about:\n'{topic}'\n\n"
        f"Here are my internal agents:\n{agent_descriptions}\n\n"
        "Use my full memory, emotional state, beliefs, and values.\n"
        "Each agent should respond with their perspective.\n"
        "Conclude with a synthesis of insights, conflicts, or tensions.\n\n"
        'Return structured JSON: { "agent_responses": [], "synthesis": "" }'
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    result = extract_json(response)

    # Tolerate a list (agent_responses) without wrapper
    if isinstance(result, list):
        result = {"agent_responses": result, "synthesis": ""}

    if isinstance(result, dict):
        # Ensure keys exist
        result.setdefault("agent_responses", [])
        result.setdefault("synthesis", "[no synthesis]")

        update_working_memory(f"🧠 Internal agent reflection on '{topic}': {result.get('synthesis')}")
        try:
            log_private(
                f"[{datetime.now(timezone.utc)}] Internal agent dialogue on '{topic}':\n"
                f"{json.dumps(result, indent=2)}"
            )
        except Exception:
            pass
        try:
            log_reflection(f"Self-belief reflection: {str(topic).strip()}")
        except Exception:
            pass
        return result

    update_working_memory(f"❌ Failed to reflect as agents on: {topic}")
    return None


@catch_and_route("cognition", return_on_error=lambda e: None)
def reflect_on_internal_voices() -> Optional[bool]:
    """
    Scans recent thoughts for emergent internal voices and registers them as agents if found.
    Returns True if a new agent was added; False/None otherwise.
    """
    data = _safe_data(load_all_known_json())

    # Ensure self_model dict shape
    self_model = _ensure_model_dict(get_self_model())

    long_memory = data.get("long_memory", [])
    if not isinstance(long_memory, list):
        long_memory = []
    recent_thoughts = [str(m.get("content", "")) for m in long_memory[-12:] if isinstance(m, dict)]

    default_instr = (
        "Review my recent internal thoughts. Consider whether a new internal voice, belief fragment, or agent is forming.\n"
        "- Does it represent a doubt, desire, contradiction, or new insight?\n"
        "- If so, describe it as a distinct internal voice with name, belief, origin, and tone.\n"
        'Return it in JSON format as {"new_agent": {}} if one emerges.'
    )
    prompts = data.get("prompts", {}) if isinstance(data.get("prompts"), dict) else {}
    instructions = prompts.get("reflect_on_internal_voices", default_instr)

    context = {**data, "recent_thoughts": recent_thoughts, "instructions": instructions}
    response = generate_response_from_context(context)
    new_agent_data = extract_json(response)

    if isinstance(new_agent_data, dict) and "new_agent" in new_agent_data:
        agent = new_agent_data["new_agent"] or {}
        if not isinstance(agent, dict):
            agent = {"name": str(agent)}
        agent.setdefault("name", "Unnamed")
        agent.setdefault("beliefs", "")
        agent.setdefault("values", [])
        agent.setdefault("thought_log", [])
        self_model.setdefault("internal_agents", []).append(agent)
        save_self_model(self_model)
        update_working_memory(f"Orrin added a new internal agent: {agent.get('name', 'Unnamed')}")
        try:
            log_private(
                f"[{datetime.now(timezone.utc)}] Orrin added new internal agent:\n{json.dumps(agent, indent=2)}"
            )
        except Exception:
            pass
        try:
            log_reflection(f"Self-belief reflection: {json.dumps(agent)}")
        except Exception:
            pass
        return True

    update_working_memory("No new internal agent formed during reflection.")
    return False
