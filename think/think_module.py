from utils.manage_cycle_count import manage_cycle_count
from think.think_utils.dreams_emotional_logic import dreams_and_emotional_logic
from think.think_utils.reflect_on_directive import reflect_on_directive
from think.think_utils.select_function import select_function
from think.think_utils.finalize import finalize_cycle
from cognition.selfhood.self_model_conflicts import update_self_model
from utils.json_utils import load_json
from utils.emotion_utils import dominant_emotion
from emotion.emotion_learning import update_emotion_function_map
from behavior.speak import OrrinSpeaker
from cognition.selfhood.relationships import update_relationship_model
from registry.cognition_registry import COGNITIVE_FUNCTIONS
from think.think_utils.execute_cogntive_actions import execute_cognitive_action

from paths import (
    SELF_MODEL_FILE,
    LONG_MEMORY_FILE,
    TOOL_REQUESTS_FILE,
    COGNITION_STATE_FILE,
    COGNITION_HISTORY_FILE,
    RELATIONSHIPS_FILE,
)

def think(context):
    import traceback
    import time
    cycle_start_time = time.perf_counter()

    try:
        # === 0. MANAGE CYCLE COUNT (always first, never skipped) ===
        context, cycle_count = manage_cycle_count(context)
        
        # === 1. LOAD CRITICAL STATE ===
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

        # === 2. DREAMS & EMOTIONAL LOGIC (never skipped) ===
        context, emotional_state, amygdala_response = dreams_and_emotional_logic(context)

        # === 3. Handle prioritized signals (already processed by thalamus) ===
        top_signals = context.get("top_signals", [])
        attention_mode = context.get("attention_mode", "neutral")
        context["filtered_signals"] = top_signals  # backwards compatibility

        # Optional: Update relationship model based on recent interaction patterns
        update_relationship_model(context)

        # === 4. REFLECT ON DIRECTIVE ===
        directive_result = reflect_on_directive(self_model, context)

        # === 5. SELECT COGNITIVE FUNCTION ===
        available_functions = context.get("available_functions") or COGNITIVE_FUNCTIONS
        context["available_functions"] = available_functions

        next_function, reason, is_action = select_function(
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

        # Get the current dominant emotion (from the up-to-date emotional_state)
        dom_emotion = dominant_emotion(emotional_state)
        fn_name = (
            next_function.get("name")
            if isinstance(next_function, dict) and "name" in next_function
            else str(next_function)
        )
        if dom_emotion and fn_name:
            update_emotion_function_map(dom_emotion, fn_name)

        # === 6. EXECUTE COGNITIVE ACTION (always, internal) ===
        if is_action and isinstance(next_function, dict):
            execute_cognitive_action(next_function, context)

        # === 7. BASAL GANGLIA: ACTION SELECTION ===
        from think.think_utils.action_gate import evaluate_and_act_if_needed

        _ = evaluate_and_act_if_needed(
            context,
            emotional_state=emotional_state,
            long_memory=long_memory,
            speaker=speaker
        )

        # === 8. FINALIZE CYCLE ===
        user_input = context.get("latest_user_input")
        context_hash = hash(str(self_model) + str(emotional_state) + str(long_memory[-5:]))
        _ = finalize_cycle(
            context,
            user_input,
            next_function,
            reason,
            context_hash,
            speaker
        )

        # === 9. UPDATE SELF MODEL (must happen here or after reflection/goal update) ===
        update_self_model()

        # === 10. Update context with all critical, potentially mutated objects ===
        context["self_model"] = self_model
        context["long_memory"] = long_memory
        context["emotional_state"] = emotional_state
        context["working_memory"] = working_memory
        context["cycle_count"] = cycle_count
        context["last_think_time"] = time.time()
        context["last_cycle_duration"] = time.perf_counter() - cycle_start_time

        # === 11. (Optional) Clear per-cycle temporary state ===
        context.pop("filtered_signals", None)
        # Add any more per-cycle keys you want to clear.

        # --- PATCH: Return next_function, reason, is_action, context, and action dict if needed ---
        if is_action:
            return {
                "action": {"name": fn_name, "details": next_function},
                "context": context,
            }
        else:
            return {
                "next_function": fn_name,
                "reason": reason,
                "is_action": is_action,
                "context": context,
            }

    except Exception as e:
        import traceback
        from utils.log import log_error
        log_error(f"THINK() CRASHED: {e}\n{traceback.format_exc()}")
        context["last_think_error"] = str(e)
        return context