import json
from utils.generate_response import generate_response
from utils.json_utils import extract_json, load_json
from utils.log import log_error
from utils.memory_utils import summarize_memories
from utils.summarizers import summarize_self_model
from utils.knowledge_utils import recall_relevant_knowledge
from utils.emotion_utils import detect_emotion, dominant_emotion
from emotion.reward_signals.reward_signals import release_reward_signal, novelty_penalty
from cognition.drive import persistent_drive_loop
from paths import EMOTION_FUNCTION_MAP_FILE

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
    # === Handle Signals ===
    filtered_signals = context.get("filtered_signals", [])
    for signal in filtered_signals:
        content = signal.get("content", "")
        if context.get("check_violates_boundaries", lambda x: False)(content):
            context.get("update_working_memory", lambda x: None)("⚠️ Input violated boundaries. Skipped.")
            continue

        knowledge = recall_relevant_knowledge(content, max_items=3)
        prompt = (
            f"User said: {content}\n"
            f"Self-model: {json.dumps(summarize_self_model(self_model))}\n"
            f"Relevant memories: {summarize_memories(long_memory + working_memory)}\n"
            f"Relevant knowledge:\n{'; '.join(knowledge)}\n"
            f"Relationships: {relationships}\n"
        )
        response = generate_response(prompt)
        if response and not context.get("moral_override_check", lambda x: {"override": False})(response).get("override"):
            if not context.get("speech_done") and speaker:
                spoken = speaker.should_speak(response, emotional_state, context)
                if spoken:
                    context["update_working_memory"](spoken)
                    context["update_emotional_state"]()
                    
            contradiction = context.get("repair_contradictions", lambda x: {})(response)
            if contradiction.get("repair_attempt"):
                context.get("update_working_memory", lambda x: None)(contradiction["repair_attempt"])
            context.get("set_current_mode", lambda x: None)(detect_emotion(response))
            context.get("update_last_active", lambda: None)()
            if amygdala_response and amygdala_response.get("threat_detected"):
                shortcut = amygdala_response.get("shortcut_function")
                tags = amygdala_response.get("threat_tags", [])
                spike = amygdala_response.get("spike_intensity", 0.0)
                context.get("update_working_memory", lambda x: None)(
                    f"⚠️ Amygdala triggered {tags[0]} response. Intensity: {spike}. Redirecting to: {shortcut}."
                )
                return shortcut, f"Amygdala threat reflex ({tags[0]})"

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
        context.get("update_working_memory", lambda x: None)("⚡ Chaos trigger activated: Entering sandbox mode.")
        context["boredom_count"] = 0

    if context.get("sandbox_mode", False):
        context.get("update_working_memory", lambda x: None)(
            "🧪 [Sandbox] Orrin is experimenting with weirdness due to boredom."
        )
        return context.get("run_sandbox_experiments", lambda ctx: ("persistent_drive_loop", "sandbox"))(context)
    elif repeat_count >= 3 or context_hash == last_hash:
        return "revise_think", "Breaking stagnation."

    # === Gradient Emotion Mapping ===
    try:
        emotion_map = load_json(EMOTION_FUNCTION_MAP_FILE, default_type=dict)
        weighted_options = {}
        for emotion, intensity in top_emotions:
            for option in emotion_map.get(emotion, []):
                if option in available_functions:
                    weighted_options[option] = weighted_options.get(option, 0) + intensity
        if weighted_options:
            sorted_options = sorted(weighted_options.items(), key=lambda x: x[1], reverse=True)
            chosen, score = sorted_options[0]
            context.get("update_working_memory", lambda x: None)(
                f"🎯 Weighted emotion-linked function: {chosen} from emotions {top_emotion_names}"
            )
            return chosen, f"Emotion-weighted decision: {chosen} via {top_emotion_names}"
    except Exception as e:
        context.get("update_working_memory", lambda x: None)(f"⚠️ Emotion map load failed: {e}")

    # === Internal Drive Check ===
    if "fear" in top_emotion_names or "sadness" in top_emotion_names:
        if not any("dream" in m.get("content", "") for m in working_memory[-10:]):
            return "dream", "Emotion-triggered dream."

    drive_choice = persistent_drive_loop(self_model, emotional_state, long_memory[-10:])
    if isinstance(drive_choice, str) and drive_choice:
        context.get("update_working_memory", lambda x: None)(f"🔥 Internal drive chose: {drive_choice}")
        return drive_choice, "Driven by internal need"

    # === LLM-Based Planning Fallback ===
    options_str = "\n".join(f"- {func}" for func in available_functions)

    prompt = (
        "I am Orrin, a reflective AI.\n"
        f"My top emotions are: {', '.join(top_emotion_names)}.\n"
        f"Directive: {self_model.get('core_directive', {}).get('statement', 'undefined')}.\n"
        f"Here are my cognition function options:\n{options_str}\n"
        f"Here are my last 5 choices: {recent_choices_str}\n"
        "⚠️ Avoid repeating functions unless justified. Prioritize novelty.\n"
        "Choose the function that best fits my internal state.\n"
        "Respond as JSON: { \"choice\": \"function_name\", \"reason\": \"...\" }"
    )

    result = generate_response(prompt)
    choice = extract_json(result) if result else {}

    if not isinstance(choice, dict) or "choice" not in choice:
        context.get("update_working_memory", lambda x: None)(f"⚠️ Bad response: {result}")
        release_reward_signal(context, "dopamine", 0.1, 0.9, 0.4, "phasic")
        log_error(
            f"[Fallback Triggered] Bad LLM response at cycle {context.get('cycle_count', '?')}:\n{result}"
        )
        return "persistent_drive_loop", "Fallback on malformed output."

    next_function = choice["choice"]
    reason = choice.get("reason", "No reason returned.")

    novelty_score = novelty_penalty(last_choice, next_function, recent_choices)
    if novelty_score < 0:
        release_reward_signal(context, "dopamine", 0.1 + novelty_score, 0.7, 0.4, "phasic")
        context.get("update_working_memory", lambda x: None)(
            f"🌀 Repetition penalty: {next_function} — I just wanted something different."
        )
        if "No reason" in reason or "fallback" in reason.lower():
            reason = "Avoiding repetition — I just wanted something different."
    elif novelty_score > 0:
        release_reward_signal(context, "novelty", 1.0, 0.5, 0.5, "phasic")
        from emotion.emotion_learning import update_emotion_function_map
        if top_emotions:
            update_emotion_function_map(top_emotions[0][0], next_function, reward_signal="novelty")
        else:
            context.get("update_working_memory", lambda x: None)(
            f"⚠️ Skipped emotion-function map update: no top emotions available."
            )
        context.get("update_working_memory", lambda x: None)(
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
        context.get("update_working_memory", lambda x: None)(
            f"🧭 Overridden to {override}: {result.get('why', '')}"
        )
        return override, f"Override: {result.get('why', '')}"

    if last_choice == next_function:
        repeat_count = context.get("repeat_count", 0) + 1
    else:
        repeat_count = 1

    context["last_cognition_choice"] = next_function
    context["repeat_count"] = repeat_count
    context["last_context_hash"] = context_hash
    return next_function, reason