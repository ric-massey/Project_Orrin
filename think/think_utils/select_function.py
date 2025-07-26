import json
from utils.generate_response import generate_response
from utils.json_utils import extract_json, load_json
from utils.log import log_error
from utils.memory_utils import format_memories_for_prompt
from utils.summarizers import summarize_self_model
from utils.knowledge_utils import recall_relevant_knowledge
from utils.emotion_utils import detect_emotion, dominant_emotion
from emotion.reward_signals.reward_signals import release_reward_signal, novelty_penalty
from core.drive import persistent_drive_loop
from paths import EMOTION_FUNCTION_MAP_FILE, COGNITIVE_FUNCTIONS_LIST_FILE

def select_function(
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
    amygdala_response=None,
    speaker=None
):
    # === Defensive: ensure dict structure ===
    if not isinstance(available_functions, dict):
        available_functions = {fn: {"function": fn, "is_action": False} for fn in available_functions}

    # === Handle Signals ===
    filtered_signals = context.get("filtered_signals", [])
    for signal in filtered_signals:
        content = signal.get("content", "")

        # Only process signals from real user input, or (optional) introspective signals
        if signal.get("source") != "user_input" or not content.strip():
            continue

        if context.get("check_violates_boundaries", lambda x: False)(content):
            if callable(context.get("update_working_memory")):
                context["update_working_memory"]("⚠️ Input violated boundaries. Skipped.")
            continue

        # === UPDATED: Unified rich memory recall and marking ===
        relevant_memories = recall_relevant_knowledge(content, long_memory=long_memory, working_memory=working_memory, max_items=8)
        for mem in relevant_memories:
            mem["referenced"] = mem.get("referenced", 0) + 1
            mem["recall_count"] = mem.get("recall_count", 0) + 1

        prompt = (
            f"User said: {content}\n"
            f"Self-model: {json.dumps(summarize_self_model(self_model))}\n"
            f"Relevant memories:\n{format_memories_for_prompt(relevant_memories)}\n"
            f"Relationships: {relationships}\n"
        )
        response = generate_response(prompt)
        if response and not context.get("moral_override_check", lambda x: {"override": False})(response).get("override"):
            if not context.get("speech_done") and speaker:
                spoken = speaker.should_speak(response, emotional_state, context)
                if spoken and callable(context.get("update_working_memory")):
                    context["update_working_memory"](spoken)
                    if callable(context.get("update_emotional_state")):
                        context["update_emotional_state"]()
            contradiction = context.get("repair_contradictions", lambda x: {})(response)
            if contradiction.get("repair_attempt") and callable(context.get("update_working_memory")):
                context["update_working_memory"](contradiction["repair_attempt"])
            if callable(context.get("set_current_mode")):
                context["set_current_mode"](detect_emotion(response))
            if callable(context.get("update_last_active")):
                context["update_last_active"]()
            if amygdala_response and amygdala_response.get("threat_detected"):
                shortcut = amygdala_response.get("shortcut_function")
                tags = amygdala_response.get("threat_tags", [])
                spike = amygdala_response.get("spike_intensity", 0.0)
                if callable(context.get("update_working_memory")):
                    context["update_working_memory"](
                        f"⚠️ Amygdala triggered {tags[0]} response. Intensity: {spike}. Redirecting to: {shortcut}."
                    )
                return shortcut, f"Amygdala threat reflex ({tags[0]})", False

    # === Anti-stagnation Check ===
    core_emotions = emotional_state.get("core_emotions", {})
    top_emotions = sorted(core_emotions.items(), key=lambda x: x[1], reverse=True)[:3]
    top_emotion_names = [e[0] for e in top_emotions] if top_emotions else [dominant_emotion(emotional_state)]
    recent_choices = [entry.get("choice") for entry in cognition_log[-5:]]
    recent_choices_str = ", ".join(recent_choices) if recent_choices else "none"

    context_hash = hash(json.dumps({
        "self_model": self_model,
        "emotions": top_emotion_names,
        "pending_requests": [r for r in tool_requests if not r.get("executed")]
    }, sort_keys=True))
    last_hash = context.get("last_context_hash", "")

    BOREDOM_THRESHOLD = 3
    context.setdefault("boredom_count", 0)
    context.setdefault("sandbox_mode", False)
    if last_choice == context.get("last_cognition_choice"):
        repeat_count = context.get("repeat_count", 0) + 1
    else:
        repeat_count = 1

    if repeat_count >= 2 or context_hash == last_hash:
        context["boredom_count"] += 1
    else:
        context["boredom_count"] = 0

    if context["boredom_count"] >= BOREDOM_THRESHOLD:
        context["sandbox_mode"] = True
        if callable(context.get("update_working_memory")):
            context["update_working_memory"]("⚡ Chaos trigger activated: Entering sandbox mode.")
        context["boredom_count"] = 0

    if context.get("sandbox_mode", False):
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](
                "🧪 [Sandbox] Orrin is experimenting with weirdness due to boredom."
            )
        func_name, reason = context.get("run_sandbox_experiments", lambda ctx: ("persistent_drive_loop", "sandbox"))(context)
        return func_name, reason, False
    elif repeat_count >= 3 or context_hash == last_hash:
        return "revise_think", "Breaking stagnation.", False

    # === Gradient Emotion Mapping ===
    try:
        emotion_map = load_json(EMOTION_FUNCTION_MAP_FILE, default_type=dict)
        weighted_options = {}
        for emotion, intensity in top_emotions:
            for option in emotion_map.get(emotion, []):
                if option in available_functions.keys():
                    weighted_options[option] = weighted_options.get(option, 0) + intensity
        if weighted_options:
            sorted_options = sorted(weighted_options.items(), key=lambda x: x[1], reverse=True)
            chosen, score = sorted_options[0]
            if callable(context.get("update_working_memory")):
                context["update_working_memory"](
                    f"🎯 Weighted emotion-linked function: {chosen} from emotions {top_emotion_names}"
                )
            is_action = available_functions.get(chosen, {}).get("is_action", False)
            return chosen, f"Emotion-weighted decision: {chosen} via {top_emotion_names}", is_action
    except Exception as e:
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](f"⚠️ Emotion map load failed: {e}")

    # === Internal Drive Check ===
    if "fear" in top_emotion_names or "sadness" in top_emotion_names:
        if not any("dream" in m.get("content", "") for m in working_memory[-10:]):
            return "dream", "Emotion-triggered dream.", False

    drive_choice = persistent_drive_loop(self_model, emotional_state, long_memory[-10:])
    if isinstance(drive_choice, str) and drive_choice:
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](f"🔥 Internal drive chose: {drive_choice}")
        is_action = available_functions.get(drive_choice, {}).get("is_action", False)
        return drive_choice, "Driven by internal need", is_action

    # === LLM-Based Planning Fallback with Forced Validation ===
    try:
        func_descriptions = load_json(COGNITIVE_FUNCTIONS_LIST_FILE, default_type=list)
        formatted_options = [
            f"- {entry['name']}: {entry.get('summary', 'No summary.')}"
            for entry in func_descriptions
            if entry['name'] in available_functions.keys()
        ]
        if not formatted_options:
            raise ValueError("No valid function descriptions matched available_functions.")
        options_str = "\n".join(formatted_options)
    except Exception as e:
        log_error(f"⚠️ Failed to load function summaries for fallback prompt: {e}")
        options_str = "\n".join(f"- {func}" for func in available_functions.keys())

    def strict_choice_prompt(warning=""):
        prompt = (
            "I am Orrin, a reflective AI.\n"
            f"My top emotions are: {', '.join(top_emotion_names)}.\n"
            f"Directive: {self_model.get('core_directive', {}).get('statement', 'undefined')}.\n"
            f"Here are my cognition function options:\n{options_str}\n"
            f"Here are my last 5 choices: {recent_choices_str}\n"
            f"{warning}\n"
            "Respond ONLY as JSON: {{ \"choice\": \"function_name\", \"reason\": \"...\" }}\n"
            "The function name MUST be chosen from the list above EXACTLY."
        )
        result = generate_response(prompt)
        return extract_json(result) if result else {}

    choice = strict_choice_prompt("⚠️ Choose ONLY from the list above.")
    if not isinstance(choice, dict) or "choice" not in choice or choice["choice"] not in available_functions.keys():
        choice = strict_choice_prompt("❌ Invalid choice. Try again. Use EXACTLY one of the options above.")
        if not isinstance(choice, dict) or "choice" not in choice or choice["choice"] not in available_functions.keys():
            log_error("🚫 LLM hallucinated twice in fallback decision.")
            return "persistent_drive_loop", "Fallback: hallucination protection triggered.", False

    next_function = choice["choice"]
    reason = choice.get("reason", "No reason returned.")
    is_action = available_functions.get(next_function, {}).get("is_action", False)

    novelty_score = novelty_penalty(last_choice, next_function, recent_choices)
    if novelty_score < 0:
        release_reward_signal(
            context,
            signal_type="dopamine",
            actual_reward=0.1 + novelty_score,
            expected_reward=0.7,
            effort=0.4,
            mode="phasic",
            source="repetition_penalty"
        )
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](
                f"🌀 Repetition penalty: {next_function} — I just wanted something different."
            )
        if "No reason" in reason or "fallback" in reason.lower():
            reason = "Avoiding repetition — I just wanted something different."
    elif novelty_score > 0:
        release_reward_signal(
            context,
            signal_type="novelty",
            actual_reward=1.0,
            expected_reward=0.5,
            effort=0.5,
            mode="phasic",
            source="novelty_reward"
        )
        from emotion.emotion_learning import update_emotion_function_map
        if top_emotions:
            update_emotion_function_map(top_emotions[0][0], next_function, reward_signal="novelty")
        else:
            if callable(context.get("update_working_memory")):
                context["update_working_memory"](
                    f"⚠️ Skipped emotion-function map update: no top emotions available."
                )
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](
                f"🌱 Novelty reward: {next_function} — It just felt good."
            )
        if "No reason" in reason or "fallback" in reason.lower():
            reason = "Dopamine-driven curiosity — it just felt good."

    decision_check = generate_response(
        f"I am Orrin. I chose '{next_function}' because: {reason}.\n"
        "Does this align with my directive, beliefs, and emotions? Respond as JSON: { \"approved\": true/false, \"why\": \"...\", \"override_function\": \"...\" }"
    )
    result = extract_json(decision_check)
    if result and not result.get("approved", True):
        override = result.get("override_function", "reflect_on_emotions")
        if callable(context.get("update_working_memory")):
            context["update_working_memory"](
                f"🧭 Overridden to {override}: {result.get('why', '')}"
            )
        return override, f"Override: {result.get('why', '')}", False

    if last_choice == next_function:
        repeat_count = context.get("repeat_count", 0) + 1
    else:
        repeat_count = 1

    context["last_cognition_choice"] = next_function
    context["repeat_count"] = repeat_count
    context["last_context_hash"] = context_hash
    return next_function, reason, is_action