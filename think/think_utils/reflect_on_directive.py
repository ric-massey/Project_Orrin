import json
from utils.generate_response import generate_response
from utils.knowledge_utils import recall_relevant_knowledge
from utils.goals import extract_current_focus_goal
from memory.working_memory import update_working_memory
from utils.json_utils import load_json  # ✅ correct source
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import LONG_MEMORY_FILE, WORKING_MEMORY_FILE, FOCUS_GOAL

def reflect_on_directive(self_model, context=None):
    """
    Use the core directive in self_model to generate a reflection, update memory,
    and optionally inject results into context. Returns a dict with 'reflection' and 'related'.
    Rewards:
      + dopamine for good reflection
      + novelty for linking knowledge
      - dopamine for missing reflection
    """
    # Always load focus goal from disk (runtime mutability)
    try:
        focus_goal = load_json(FOCUS_GOAL, default_type=dict)
    except Exception:
        focus_goal = {}

    directive = self_model.get("core_directive", {}) if isinstance(self_model, dict) else {}
    if isinstance(directive, str):
        directive = {"statement": directive}

    if not isinstance(directive, dict) or not directive:
        # Nothing to reflect on
        if context is not None:
            context["directive_reflection"] = ""
            context["directive_related_knowledge"] = []
        return {"reflection": "", "related": []}

    # Build focus goal string
    current_goal_str = ""
    try:
        current_goal_str = extract_current_focus_goal(focus_goal) or ""
    except Exception:
        current_goal_str = ""
    focus_goal_str = f'Focus Goal: "{current_goal_str}"' if current_goal_str else "No explicit focus goal found."

    stmt = directive.get("statement") or ""
    motivations = directive.get("motivations", [])
    prompt = (
        f'My directive is: "{stmt}"\n'
        f"Motivations: {json.dumps(motivations, ensure_ascii=False)}\n\n"
        f"{focus_goal_str}\n\n"
        "Am I currently aligned with this? What should I prioritize next?"
    )

    reflection = generate_response(prompt)
    reflection_ok = isinstance(reflection, str) and len(reflection.strip()) > 2
    related = []

    if reflection_ok:
        # Load memory stores (safe defaults)
        try:
            long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        except Exception:
            long_memory = []
        try:
            working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)
        except Exception:
            working_memory = []

        # Recall relevant knowledge
        related = recall_relevant_knowledge(
            reflection or stmt,
            long_memory=long_memory,
            working_memory=working_memory,
            max_items=8
        ) or []

        # Normalize related to a list of strings for logging
        if not isinstance(related, list):
            related = [str(related)]
        else:
            related = [str(r) for r in related]

        # Log reflection and any links
        try:
            update_working_memory({
                "content": reflection.strip(),
                "event_type": "reflection",
                "importance": 2,
                "priority": 2
            })
            if related:
                update_working_memory({
                    "content": "Related conceptual knowledge: " + "; ".join(related),
                    "event_type": "knowledge_link",
                    "importance": 1,
                    "priority": 1,
                    "referenced": 1
                })
        except Exception:
            pass

        # Rewards
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
            if related:
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
        # Low reward if no reflection produced
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

    # Inject into context
    if context is not None:
        context["directive_reflection"] = reflection.strip() if reflection_ok else ""
        context["directive_related_knowledge"] = related

    return {"reflection": reflection.strip() if reflection_ok else "", "related": related}