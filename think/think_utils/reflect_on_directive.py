import json
from utils.generate_response import generate_response
from utils.knowledge_utils import recall_relevant_knowledge
from memory.working_memory import update_working_memory

def reflect_on_directive(self_model):
    """
    Uses the core directive in self_model to generate a reflection, update memory,
    and log related conceptual knowledge.
    Returns the reflection text (or None if no directive).
    """
    directive = self_model.get("core_directive", {})
    if not directive:
        return None  # Nothing to reflect on

    prompt = (
        f"My directive is: \"{directive.get('statement')}\"\n"
        f"Motivations: {json.dumps(directive.get('motivations', []))}\n\n"
        "Am I currently aligned with this? What should I prioritize next?"
    )
    reflection = generate_response(prompt)
    if reflection:
        related = recall_relevant_knowledge(reflection)
        update_working_memory(reflection)
        if related:
            update_working_memory(f"Related conceptual knowledge: {related}")
    return reflection