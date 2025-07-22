import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.json_utils import (
    load_json, save_json, extract_json
)
from utils.self_model import get_self_model, save_self_model
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private
from utils.log_reflection import log_reflection
from paths import SELF_MODEL_FILE

def reflect_on_internal_agents():
    """
    Reviews existing internal agents within Orrin's self-model and updates their current views
    based on recent internal events, cognitive/emotional state, and belief consistency.
    """
    self_model = get_self_model()
    data = load_all_known_json()
    agents = self_model.get("internal_agents", [])
    updated = False

    for agent in agents:
        recent_thoughts = agent.get("thought_log", [])[-3:]
        name = agent.get("name", "Unknown")
        belief = agent.get("beliefs", "")
        current_view = agent.get("current_view", "")

        instructions = (
            f"I am reflecting on my internal perspective called '{name}'.\n"
            f"This view holds a belief:\n> {belief}\n\n"
            "It has recently been thinking:\n" +
            "\n".join(f"- {t}" for t in recent_thoughts) +
            "\n\nUpdate its current view based on:\n"
            "- Its belief\n"
            "- Recent internal events\n"
            "- My emotional and cognitive state\n"
            "- Any contradiction with values, outcomes, or other agents\n"
            "Does this view still serve my goals? Should it evolve?"
        )

        context = {
            **data,
            "agent_name": name,
            "agent_belief": belief,
            "recent_thoughts": recent_thoughts,
            "current_view": current_view,
            "instructions": instructions
        }

        response = generate_response_from_context(context)

        if response:
            agent["current_view"] = response.strip()
            updated = True

    if updated:
        self_model["internal_agents"] = agents
        save_self_model(self_model)
        log_private("🧠 Orrin updated internal agent perspectives.")
        log_reflection(f"Self-belief reflection: {json.dumps(agents)}")
        update_working_memory("Orrin revised one or more internal agent views.")
    else:
        update_working_memory("No changes made to internal agent views.")

def reflect_as_agents(topic: str):
    """
    Invokes internal agent dialogue about a given topic.
    Each agent provides a perspective based on its values, role, and influence.
    Orrin synthesizes these into a unified or conflicting reflection.
    """
    data = load_all_known_json()
    self_model = data.get("self_model", {})
    agents = self_model.get("internal_agents", [])

    if not agents:
        update_working_memory(f"Orrin has no internal agents to reflect on: {topic}")
        return None

    agent_descriptions = "\n".join(
        f"- {agent.get('name', 'Unnamed')} "
        f"({agent.get('role', 'unknown')}, values: {', '.join(agent.get('values', []))}, "
        f"influence: {agent.get('influence_score', 0.5)})"
        for agent in agents
    )

    prompt = (
        f"I am Orrin, engaging in internal dialogue about:\n'{topic}'\n\n"
        f"Here are my internal agents:\n{agent_descriptions}\n\n"
        "Use my full memory, emotional state, beliefs, and values.\n"
        "Each agent should respond with their perspective.\n"
        "Conclude with a synthesis of insights, conflicts, or tensions.\n\n"
        "Return structured JSON:\n"
        "{ \"agent_responses\": [...], \"synthesis\": \"...\" }"
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    result = extract_json(response)

    if result:
        synthesis = result.get("synthesis", "[no synthesis]")
        update_working_memory(f"🧠 Internal agent reflection on '{topic}': {synthesis}")
        log_private(
            f"[{datetime.now(timezone.utc)}] Orrin's internal agent dialogue on '{topic}':\n"
            f"{json.dumps(result, indent=2)}"
        )
        log_reflection(f"Self-belief reflection: {topic.strip()}")
    else:
        update_working_memory(f"❌ Failed to reflect as agents on: {topic}")

    return result

def reflect_on_internal_voices():
    """
    Reflects on recent thoughts to detect emergence of new internal voices (fragments, doubts, drives).
    If found, adds as a new internal agent in the self-model and logs it.
    """
    data = load_all_known_json()
    self_model = get_self_model()
    long_memory = data.get("long_memory", [])
    recent_thoughts = [m["content"] for m in long_memory[-12:] if "content" in m]

    instructions = (
        "Review my recent internal thoughts. Consider whether a new internal voice, belief fragment, or agent is forming.\n"
        "- Does it represent a doubt, desire, contradiction, or new insight?\n"
        "- If so, describe it as a distinct internal voice with name, belief, origin, and tone.\n"
        "Return it in JSON format as {\"new_agent\": {...}} if one emerges."
    )

    context = {
        **data,
        "recent_thoughts": recent_thoughts,
        "instructions": data.get("prompts", {}).get("reflect_on_internal_voices", instructions)
    }

    response = generate_response_from_context(context)
    new_agent_data = extract_json(response)

    if new_agent_data and "new_agent" in new_agent_data:
        agent = new_agent_data["new_agent"]
        self_model.setdefault("internal_agents", []).append(agent)
        save_self_model(self_model)
        update_working_memory(f"Orrin added a new internal agent: {agent.get('name', 'Unnamed')}")
        log_private(
            f"[{datetime.now(timezone.utc)}] Orrin added new internal agent:\n{json.dumps(agent, indent=2)}"
        )
        log_reflection(f"Self-belief reflection: {json.dumps(agent)}")
    else:
        update_working_memory("No new internal agent formed during reflection.")