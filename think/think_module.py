from utils.manage_cycle_count import manage_cycle_count
from think.think_utils.dreams_emotional_logic import dreams_and_emotional_logic
from think.think_utils.reflect_on_directive import reflect_on_directive
from think.think_utils.select_function import select_function
from think.think_utils.finalize import finalize_cycle

from utils.json_utils import load_json
from cognition.speak import OrrinSpeaker
from selfhood.relationships import update_relationship_model
from registry.cognition_registry import COGNITIVE_FUNCTIONS
from paths import (
    SELF_MODEL_FILE,
    LONG_MEMORY_FILE,
    TOOL_REQUESTS_FILE,
    COGNITION_STATE_FILE,
    COGNITION_HISTORY_FILE,
    RELATIONSHIPS_FILE,
)

def think(context):
    # === 0. LOAD CRITICAL STATE ===
    self_model = load_json(SELF_MODEL_FILE, default_type=dict)
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    tool_requests = load_json(TOOL_REQUESTS_FILE, default_type=list)
    cognition_state = load_json(COGNITION_STATE_FILE, default_type=dict)
    cognition_log = load_json(COGNITION_HISTORY_FILE, default_type=list)
    relationships = load_json(RELATIONSHIPS_FILE, default_type=dict)
    last_choice = cognition_state.get("last_cognition_choice", None)

    # Inject into context
    context["relationships"] = relationships

    # Pull out other necessary context items
    working_memory = context.get("working_memory", [])
    update_working_memory = context.get("update_working_memory")
    check_violates_boundaries = context.get("check_violates_boundaries")
    summarize_relationships = context.get("summarize_relationships")
    speaker = context.get("speaker", OrrinSpeaker(self_model, long_memory))

    # === 1. MANAGE CYCLE COUNT ===
    context, cycle_count = manage_cycle_count(context)

    # === 2. DREAMS & EMOTIONAL LOGIC ===
    context, emotional_state, amygdala_response = dreams_and_emotional_logic(context)

    # === 3. Handle prioritized signals (already processed by thalamus) ===
    top_signals = context.get("top_signals", [])
    attention_mode = context.get("attention_mode", "neutral")
    context["filtered_signals"] = top_signals  # backwards compatibility with prior use

    # Optional: Update relationship model based on recent interaction patterns
    update_relationship_model(context)

    # === 4. REFLECT ON DIRECTIVE ===
    reflect_on_directive(self_model)

    # === 4.5 BASAL GANGLIA: ACTION SELECTION ===
    from think.think_utils.action_gate import evaluate_and_act_if_needed

    action_result = evaluate_and_act_if_needed(
        context,
        emotional_state=emotional_state,
        long_memory=long_memory,
        speaker=speaker
    )

    if isinstance(action_result, dict) and "action" in action_result:
        return action_result  # Let main loop handle it

    # === 5. SELECT FUNCTION ===
    available_functions = context.get("available_functions") or COGNITIVE_FUNCTIONS
    context["available_functions"] = available_functions

    next_function, reason = select_function(
        context,
        self_model,
        emotional_state,
        long_memory,
        working_memory,
        relationships,
        available_functions,
        last_choice,
        cognition_log,
        tool_requests,
        amygdala_response=amygdala_response,
        speaker=speaker
    )

    # === 6. FINALIZE CYCLE ===
    user_input = context.get("latest_user_input")
    context_hash = hash(str(self_model) + str(emotional_state) + str(long_memory[-5:]))
    action = finalize_cycle(
        context,
        user_input,
        next_function,
        reason,
        context_hash,
        speaker
    )

    return action