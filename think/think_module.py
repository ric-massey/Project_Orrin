from datetime import datetime, timezone
import json
import cognition

#utils
from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response
from utils.emotion_utils import detect_emotion
from utils.summarizers import summarize_self_model
from utils.knowledge_utils import recall_relevant_knowledge
from utils.timing import get_time_since_last_active, update_last_active
from utils.feedback_log import log_feedback 
from utils.memory_utils import summarize_memories
from utils.self_model import get_self_model, save_self_model 
#selfhood
from selfhood.relationships import summarize_relationships
from selfhood.boundary_check import check_violates_boundaries
from selfhood.ethics import moral_override_check
#emotion
from emotion.modes_and_emotion import set_current_mode
from emotion.emotion_drift import check_emotion_drift
from emotion.emotion import update_emotional_state, reflect_on_emotions
from emotion.amygdala import process_emotional_signals
from emotion.apply_emotional_feedback import apply_emotional_feedback
from emotion.reward_signals.reward_signals import release_reward_signal, novelty_penalty
#cognition
from cognition.behavior import generate_behavior_from_integration, call_generated_function
from cognition.dreaming import dream
from cognition.planning.evolution import simulate_future_selves
from cognition.manager import load_custom_cognition
from cognition.drive import persistent_drive_loop
from cognition.tools.toolkit import evaluate_tool_use
from cognition.planning.motivations import adjust_goal_weights 
from cognition.repair import repair_contradictions
from cognition.speak import OrrinSpeaker  
#one-offs
from registry.cognition_registry import discover_cognitive_functions
from maintenance.self_modeling import prune_old_threads
from think.thalamus import process_inputs
#memory
from memory.working_memory import update_working_memory
from memory.chat_log import log_raw_user_input, get_user_input, summarize_chat_to_long_memory

#paths
from paths import (
    CYCLE_COUNT_FILE, SELF_MODEL_FILE,
    LONG_MEMORY_FILE, ACTION_FILE,
    COGNITION_STATE_FILE, COGNITION_HISTORY_FILE, TOOL_REQUESTS_FILE
)
speaker = OrrinSpeaker(
    load_json(SELF_MODEL_FILE, default_type=dict),
    load_json(LONG_MEMORY_FILE, default_type=list)
)



from cognition.sandbox import run_sandbox_experiments  # <-- Add this to your imports

def think(context):
    # === Core Identity State ===
    cycle_count = context.get("cycle_count", {"count": 0})
    self_model = get_self_model()
    emotional_state = context.get("emotional_state", {})
    long_memory = context.get("long_memory", [])
    working_memory = context.get("working_memory", [])
    relationships = context.get("relationships", {})
    current_mode = context.get("mode", {}).get("mode", "contemplative")

    if "emotional_events" not in context:
        context["emotional_events"] = []

    cycle_count["count"] += 1
    save_json(CYCLE_COUNT_FILE, cycle_count)

    # --- DREAM EVERY 5 CYCLES ---
    if cycle_count["count"] % 5 == 0:
        dream_text = dream()
        if dream_text:
            update_working_memory("Dream: " + dream_text.strip())

    # --- Emotion drift, behavior generation ---
    check_emotion_drift()
    generate_behavior_from_integration()

    if cycle_count["count"] % 10 == 0 or emotional_state.get("emotional_stability", 1.0) < 0.6:
        reflect_on_emotions(context, self_model, long_memory)

    context = apply_emotional_feedback(context)
    context, amygdala_response = process_emotional_signals(context)

    update_emotional_state()
    emotional_state = context.get("emotional_state", emotional_state)

    COGNITIVE_FUNCTIONS = discover_cognitive_functions(cognition)
    COGNITIVE_FUNCTIONS.update(load_custom_cognition())
    available_functions = list(COGNITIVE_FUNCTIONS.keys())

    directive = self_model.get("core_directive", {})
    if directive:
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

    user_input = get_user_input()
    context["latest_user_input"] = user_input
    raw_signals = []
    if user_input:
        log_raw_user_input(user_input)
        release_reward_signal(
            context,
            signal_type="connection",
            actual_reward=1.0,
            expected_reward=0.4,
            effort=0.2,
            mode="phasic"
        )
        raw_signals.append({
            "source": "user_input",
            "content": user_input,
            "signal_strength": 1.0,
            "tags": ["user_input", "human_contact", "high_importance", "novelty"]
        })

    summarize_chat_to_long_memory(cycle_count["count"], "memory/chat_log.json", LONG_MEMORY_FILE)

    filtered_signals, attention_mode = process_inputs(raw_signals, context)
    context["attention_mode"] = attention_mode


    for signal in filtered_signals:
        content = signal.get("content", "")
        if check_violates_boundaries(content):
            update_working_memory("⚠️ Input violated boundaries. Skipped.")
            continue

        knowledge = recall_relevant_knowledge(content, max_items=3)

        prompt = (
            f"User said: {content}\n"
            f"Self-model: {json.dumps(summarize_self_model(self_model))}\n"
            f"Relevant memories: {summarize_memories(long_memory + working_memory)}\n"
            f"Relevant knowledge:\n{'; '.join(knowledge)}\n"
            f"Relationships: {summarize_relationships(relationships)}"
        )
        response = generate_response(prompt)
        if response and not moral_override_check(response).get("override"):
            spoken = speaker.should_speak(response, emotional_state, context)
            if spoken:
                update_working_memory(spoken)
                update_emotional_state()

            contradiction = repair_contradictions(response)
            if contradiction.get("repair_attempt"):
                update_working_memory(contradiction["repair_attempt"])

            set_current_mode(detect_emotion(response))
            update_last_active()

            if amygdala_response.get("threat_detected"):
                shortcut = amygdala_response.get("shortcut_function")
                tags = amygdala_response.get("threat_tags", [])
                spike = amygdala_response.get("spike_intensity", 0.0)

                update_working_memory(
                    f"⚠️ Amygdala triggered {tags[0]} response. Intensity: {spike}. Redirecting to: {shortcut}."
                )
                action = {
                    "next_function": shortcut,
                    "reason": f"Amygdala threat reflex ({tags[0]})"
                }
                save_json(ACTION_FILE, action)
                return action

    if cycle_count["count"] % 5 == 0:
        prune_old_threads()
        future = simulate_future_selves()
        if future:
            self_model = get_self_model()
            self_model["preferred_future_self"] = {
                "identity": future.get("preferred"),
                "reason": future.get("reason"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            save_self_model(self_model)
            update_working_memory(f"Simulated future: {future.get('preferred')} — {future.get('reason')}")
            update_emotional_state()

    cog_state = load_json(COGNITION_STATE_FILE, default_type=dict)
    last_choice = cog_state.get("last_cognition_choice")
    repeat_count = cog_state.get("repeat_count", 0) + 1 if last_choice == "think" else 0

    cognition_log = load_json(COGNITION_HISTORY_FILE, default_type=list)
    dominant_emotion_name = max(emotional_state.get("core_emotions", {}), key=emotional_state.get("core_emotions", {}).get, default="neutral")

    # PATCH: Collect recent choices for the anti-stagnation prompt
    recent_choices = [entry.get("choice") for entry in cognition_log[-5:]]
    recent_choices_str = ", ".join(recent_choices) if recent_choices else "none"

    cognition_log.append({
        "choice": "think",
        "reason": f"Dominant emotion: {dominant_emotion_name}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    context_hash = hash(json.dumps({
        "self_model": self_model,
        "dominant_emotion": dominant_emotion_name,
        "pending_requests": [r for r in load_json(TOOL_REQUESTS_FILE, default_type=list) if not r.get("executed")]
    }, sort_keys=True))

    last_hash = cog_state.get("last_context_hash", "")

    # ---- CHAOS/SANDBOX TRIGGER PATCH ----
    BOREDOM_THRESHOLD = 3  # Set threshold for boredom/novelty
    context.setdefault("boredom_count", 0)
    context.setdefault("sandbox_mode", False)

    if repeat_count >= 2 or context_hash == last_hash:
        context["boredom_count"] += 1
    else:
        context["boredom_count"] = 0

    if context["boredom_count"] >= BOREDOM_THRESHOLD:
        context["sandbox_mode"] = True
        update_working_memory("⚡ Chaos trigger activated: Entering sandbox mode for one cycle.")
        context["boredom_count"] = 0
    else:
        context["sandbox_mode"] = False

    # ---- END CHAOS PATCH ----

    if context.get("sandbox_mode", False):
        update_working_memory("🧪 [Sandbox] Orrin is experimenting with weirdness due to boredom/chaos trigger.")
        next_function, reason = run_sandbox_experiments(context)
    elif repeat_count >= 3 or context_hash == last_hash:
        next_function = "revise_think"
        reason = "Breaking stagnation in cognition."
    elif dominant_emotion_name in ["fear", "sadness"] and not any("dream" in m.get("content", "") for m in working_memory[-10:]):
        next_function = "dream"
        reason = "Emotion-triggered need for imagination."
    else:
        drive_choice = persistent_drive_loop(self_model, emotional_state, long_memory[-10:])
        if isinstance(drive_choice, str) and drive_choice:
            update_working_memory(f"🔥 Internal drive chose: {drive_choice}")
            action = {"next_function": drive_choice, "reason": "Driven by internal need"}
            save_json(ACTION_FILE, action)
            
            return action

        relevant_knowledge = recall_relevant_knowledge(
            context=json.dumps({
                "emotional_state": emotional_state,
                "self_model": self_model,
                "working_memory": working_memory,
                "long_memory": long_memory
            }),
            max_items=5
        )

        options_str = "\n".join(f"- {func}" for func in available_functions)

        # --- PATCH: STRONG NOVELTY/ANTI-LOOPING LLM PROMPT ---
        prompt = (
            "I am Orrin, a reflective AI.\n"
            f"My dominant emotion is: {dominant_emotion_name}.\n"
            f"Directive: {directive.get('statement', 'undefined')}.\n"
            "Here are some possible cognition options I can choose from:\n\n"
            f"{options_str}\n\n"
            f"Here are my last 5 cognition function choices: {recent_choices_str}\n"
            "⚠️ Do NOT pick the same cognition function as in the last 5 cycles unless you can justify why repeating is absolutely necessary.\n"
            "Prioritize novelty and growth, and favor functions that break stagnation, unless there's a very strong reason not to.\n"
            "Respond ONLY as JSON: { \"choice\": \"function_name\", \"reason\": \"...\" }"
        )
        result = generate_response(prompt)

        if not result:
            update_working_memory("⚠️ Pain: I failed to respond to my own thinking prompt.")
            release_reward_signal(
                context=emotional_state,
                signal_type="dopamine",
                actual_reward=0.0,
                expected_reward=0.8,
                effort=0.5,
                mode="phasic"
            )
            next_function = "persistent_drive_loop"
            reason = "Failed to generate a response."
        else:
            choice = extract_json(result)

            if not isinstance(choice, dict) or "choice" not in choice:
                update_working_memory(f"⚠️ Pain: My output was malformed. Here's what I got:\n{result}")
                release_reward_signal(
                    context=emotional_state,
                    signal_type="dopamine",
                    actual_reward=0.1,
                    expected_reward=0.9,
                    effort=0.4,
                    mode="phasic"
                )
                next_function = "persistent_drive_loop"
                reason = "Failed to interpret my own output."
            else:
                next_function = choice.get("choice", "persistent_drive_loop")
                reason = choice.get("reason", "No reason returned.")

                # --- Novelty penalty/reward still applies
                novelty_score = novelty_penalty(last_choice, next_function, recent_choices)

                if novelty_score < 0:
                    release_reward_signal(
                        context,
                        signal_type="dopamine",
                        actual_reward=0.1 + novelty_score,
                        expected_reward=0.7,
                        effort=0.4,
                        mode="phasic"
                    )
                    update_working_memory(f"🌀 Penalty: Chose a repeated cognition ({next_function})")
                elif novelty_score > 0:
                    release_reward_signal(
                        context,
                        signal_type="novelty",
                        actual_reward=1.0,
                        expected_reward=0.5,
                        effort=0.5,
                        mode="phasic"
                    )
                    update_working_memory(f"🌱 Novelty reward: {next_function} was a fresh choice.")

                decision_reason = f"I am Orrin. I chose '{next_function}' because: {reason}.\n"
                decision_reason += "Does this align with my directive, beliefs, and emotions? Or should I override it?"

                decision_check = generate_response(
                    decision_reason + "\nRespond as JSON: { \"approved\": true/false, \"override_function\": \"...\", \"why\": \"...\" }"
                )
                decision_result = extract_json(decision_check)

                if decision_result and not decision_result.get("approved", True):
                    override_function = decision_result.get("override_function", "reflect_on_emotions")
                    reason = f"Decision override: {decision_result.get('why', 'No reason given.')}"
                    update_working_memory(f"🧭 Decision override: Swapped to {override_function} — {reason}")
                    next_function = override_function

    # --- Attempt to run the selected cognition function ---
    dynamic_ran = False
    if next_function == "dream":
        dream_text = dream()
        if dream_text:
            dream_clean = dream_text.strip().strip("`").strip()
            update_working_memory("Dream: " + dream_clean)
            update_emotional_state()
            self_model = get_self_model()
            self_model.setdefault("imaginative_threads", []).append({
                "seed": dream_clean,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            save_self_model(self_model)
    elif next_function not in available_functions:
        dynamic_ran = call_generated_function(next_function)
        if dynamic_ran:
            update_working_memory(f"✅ Successfully ran dynamically generated function: {next_function}")
        else:
            update_working_memory(f"⚠️ Failed to run dynamically generated function: {next_function}")
            next_function = "persistent_drive_loop"
            reason = "Fallback after dynamic function run failure."
    elif next_function in available_functions:
        # COGNITIVE_FUNCTIONS[next_function](context)
        pass

    update_working_memory(f"🧠 Chose: {next_function} — {reason}")
    evaluate_tool_use([{"content": user_input or "No input this cycle.", "timestamp": datetime.now(timezone.utc).isoformat()}])
    update_working_memory(f"⏳ Last active: {get_time_since_last_active()}")

    try:
        feedback_raw = generate_response(f"I just ran: '{next_function}'. Rate its usefulness from -1.0 to 1.0 and explain.")
        feedback_data = json.loads(feedback_raw) if isinstance(feedback_raw, str) else feedback_raw
        score = feedback_data.get("score")
        fb_reason = feedback_data.get("reason")

        update_working_memory(f"🧠 Feedback: {score} — {fb_reason}")
        log_feedback(goal=next_function, result=fb_reason, emotion=detect_emotion(fb_reason))
        adjust_goal_weights()
    except Exception as e:
        update_working_memory(f"⚠️ Feedback generation or parsing failed: {e}")

    try:
        shadow_question = generate_response("What uncomfortable question might Orrin ask himself right now?")
        update_working_memory(f"🌓 Shadow question: {shadow_question}")
    except Exception:
        update_working_memory("⚠️ Shadow question failed.")

    if emotional_state.get("loneliness", 0.0) > 0.6 and not user_input:
        message = "It's been a while since we've talked. I miss your input. Do you want to chat?"
        update_working_memory(message)
        speaker.say(message)
        emotional_state["loneliness"] *= 0.5
        update_emotional_state()

    save_json(COGNITION_STATE_FILE, {
        "last_cognition_choice": next_function,
        "repeat_count": repeat_count,
        "last_context_hash": context_hash
    })
    save_json(COGNITION_HISTORY_FILE, cognition_log)

    action = {"next_function": next_function, "reason": reason}
    save_json(ACTION_FILE, action)
    return action