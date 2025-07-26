import json
from utils.generate_response import generate_response
from utils.knowledge_utils import recall_relevant_knowledge
from memory.working_memory import update_working_memory
from utils.load_utils import load_json
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import LONG_MEMORY_FILE, WORKING_MEMORY_FILE

def reflect_on_directive(self_model, context=None):
    """
    Uses the core directive in self_model to generate a reflection, update memory,
    and optionally inject results into context. Returns a dictionary of results.
    """
    directive = self_model.get("core_directive", {})
    if not directive:
        return {"reflection": None, "related": None}

    prompt = (
        f"My directive is: \"{directive.get('statement')}\"\n"
        f"Motivations: {json.dumps(directive.get('motivations', []))}\n\n"
        "Am I currently aligned with this? What should I prioritize next?"
    )
    reflection = generate_response(prompt)
    related = None

    if reflection:
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)
        related = recall_relevant_knowledge(reflection or directive.get('statement', ''), long_memory=long_memory, working_memory=working_memory, max_items=8)
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

        # ✅ Reward for successful directive reflection
        if context:
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
        if context and related:
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
        if context:
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
        context["directive_reflection"] = reflection
        context["directive_related_knowledge"] = related

    return {
        "reflection": reflection,
        "related": related
    }