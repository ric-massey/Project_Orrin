import json
from utils.generate_response import generate_response
from utils.knowledge_utils import recall_relevant_knowledge
from memory.working_memory import update_working_memory
from utils.load_utils import load_json
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import LONG_MEMORY_FILE, WORKING_MEMORY_FILE, FOCUS_GOAL

def reflect_on_directive(self_model, context=None):
    """
    Uses the core directive in self_model to generate a reflection, update memory,
    and optionally inject results into context. Returns a dictionary of results.

    Rewards: 
    - +dopamine for good reflection
    - +novelty for linking knowledge
    - -dopamine for missing reflection
    """
    # === Always load focus goal live for AGI/runtime mutability ===
    try:
        focus_goal = load_json(FOCUS_GOAL, default_type=dict)
    except Exception:
        focus_goal = {}

    directive = self_model.get("core_directive", {})
    if not directive:
        return {"reflection": None, "related": None}

    # --- Build focus goal string safely ---
    if focus_goal and focus_goal.get('short_or_mid') or focus_goal.get('goal'):
        focus_goal_str = (
            f"Focus Goal: \"{focus_goal.get('goal', focus_goal.get('short_or_mid', ''))}\"\n"
            f"Reason: {focus_goal.get('reason', '')}\n"
            f"Milestones: {json.dumps(focus_goal.get('milestones', []), indent=2)}"
        )
    else:
        focus_goal_str = "No explicit focus goal found."

    prompt = (
        f"My directive is: \"{directive.get('statement')}\"\n"
        f"Motivations: {json.dumps(directive.get('motivations', []))}\n\n"
        f"{focus_goal_str}\n\n"
        "Am I currently aligned with this? What should I prioritize next?"
    )

    reflection = generate_response(prompt)
    related = None

    if reflection and isinstance(reflection, str) and len(reflection.strip()) > 2:
        try:
            long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        except Exception:
            long_memory = []
        try:
            working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)
        except Exception:
            working_memory = []

        related = recall_relevant_knowledge(
            reflection or directive.get('statement', ''), 
            long_memory=long_memory, 
            working_memory=working_memory, 
            max_items=8
        )
        try:
            update_working_memory({
                "content": reflection,
                "event_type": "reflection",
                "importance": 2,
                "priority": 2
            })
            if related:
                update_working_memory({
                    "content": f"Related conceptual knowledge: {related}",
                    "event_type": "knowledge_link",
                    "importance": 1,
                    "priority": 1,
                    "referenced": 1
                })
        except Exception:
            pass

        # ✅ Reward for successful directive reflection
        if context is not None:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.7,
                expected_reward=0.5,
                effort=0.6,
                mode="phasic",
                source="directive_reflection"
            )

        # Additional small reward for linking related knowledge
        if context is not None and related:
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=0.5,
                expected_reward=0.3,
                effort=0.3,
                mode="tonic",
                source="knowledge_linking"
            )

    else:
        # ⚠️ Minor penalty or low reward if no reflection produced
        if context is not None:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.1,
                expected_reward=0.5,
                effort=0.4,
                mode="phasic",
                source="reflection_failure"
            )

    if context is not None:
        context["directive_reflection"] = reflection or ""
        context["directive_related_knowledge"] = related or []

    return {
        "reflection": reflection or "",
        "related": related or []
    }