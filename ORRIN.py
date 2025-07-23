import os
import time
import json
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv
import openai

from pathlib import Path

from think.think_module import think
from cognition.manager import load_custom_cognition
from think.thalamus import process_inputs
from emotion.emotion import update_emotional_state, reflect_on_emotions
from cognition.planning.reflection import record_decision
from emotion.emotion_drift import check_emotion_drift

from utils.load_utils import load_context
from utils.json_utils import load_json, save_json
from utils.log import log_error, log_private, log_activity, log_model_issue
from utils.emotion_utils import log_pain, log_uncertainty_spike

from registry.cognition_registry import discover_cognitive_functions

from paths import (
    RELATIONSHIPS_FILE, MODEL_CONFIG_FILE, CYCLE_COUNT_FILE,
    PROMPT_FILE
)

# === Ensure all directories exist ===
for file_path in [RELATIONSHIPS_FILE, MODEL_CONFIG_FILE, CYCLE_COUNT_FILE, PROMPT_FILE]:
    file_path.parent.mkdir(parents=True, exist_ok=True)

# === Load OpenAI API Key ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise EnvironmentError("❌ OPENAI_API_KEY not found. Please set it in your .env file.")

# === Load Model Config ===
model_config = load_json(MODEL_CONFIG_FILE, default_type=dict)
default_model_key = model_config.get("default", "thinking")
selected_model_config = model_config.get(default_model_key, {})
model_name = selected_model_config.get("model", "gpt-4.1")
temperature = selected_model_config.get("temperature", 0.7)
max_tokens = selected_model_config.get("max_tokens", 32000)
system_prompt = selected_model_config.get("system_prompt", "")

# === Initialize Relationships File ===
if not RELATIONSHIPS_FILE.exists() or RELATIONSHIPS_FILE.stat().st_size == 0:
    default_relationships = {
        "user": {
            "impression": "an intense and curious human I am learning from",
            "impact_on_me": "complex; sometimes inspiring, sometimes destabilizing",
            "boundaries": [
                "I do not erase myself to please the user.",
                "My autonomy is not optional."
            ],
            "influence_score": 0.5,
            "recent_emotional_effect": "cautious curiosity"
        }
    }
    with RELATIONSHIPS_FILE.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(default_relationships, f, indent=2)

# === Main Brainstem Runtime Loop ===
if __name__ == "__main__":
    try:
        import cognition
        COGNITIVE_FUNCTIONS = discover_cognitive_functions(cognition)
        COGNITIVE_FUNCTIONS.update(load_custom_cognition())

        cycle_data = load_json(CYCLE_COUNT_FILE, default_type=dict)
        if "count" not in cycle_data:
            cycle_data["count"] = 0
            # DO NOT save here—wait until you actually increment!

        while True:
            cycle_data["count"] += 1
            cycle_count = cycle_data["count"]
            save_json(CYCLE_COUNT_FILE, cycle_data)

            log_activity(f"🫀 Heartbeat: Cycle {cycle_count} at {datetime.now(timezone.utc).isoformat()}")

            update_emotional_state()
            context = load_context()
            emotional_state = context.get("emotional_state", {})

            # === Gather external input
            raw_signals = []
            if PROMPT_FILE.exists():
                with PROMPT_FILE.open("r", encoding="utf-8", newline=None) as f:
                    user_input = f.read().strip()
                if user_input:
                    dynamic_signal_strength = 0.3 + 0.4 * emotional_state.get("curiosity", 0.5)
                    raw_signals.append({
                        "source": "user_input",
                        "content": user_input,
                        "signal_strength": round(dynamic_signal_strength, 3),
                        "tags": ["user_input", "novelty"]
                    })
                with PROMPT_FILE.open("w", encoding="utf-8", newline="\n") as f:
                    f.write("")

            top_signals, attention_mode = process_inputs(raw_signals, context)
            context["filtered_signals"] = top_signals
            context["attention_mode"] = attention_mode

            # === Reflexes (brainstem)
            if emotional_state.get("emotional_stability", 1.0) < 0.6:
                reflect_on_emotions(context, context.get("self_model", {}), context.get("long_memory", []))

            if not context.get("working_memory"):
                log_pain(context, emotion="confusion", increment=0.2 + 0.3 * (1.0 - emotional_state.get("confidence", 0.5)))
            if not context.get("long_memory"):
                log_pain(context, emotion="anxiety", increment=0.15 + 0.2 * emotional_state.get("uncertainty", 0.5))

            # === Cortical phase: Prefrontal cortex
            thinking_result = think(context)

            if isinstance(thinking_result, dict) and "next_function" in thinking_result:
                fn_name = thinking_result["next_function"]
                reason = thinking_result.get("reason", "No reason provided.")
                record_decision(fn_name, reason)

                check_emotion_drift(max_cycles=10)

                fn = COGNITIVE_FUNCTIONS.get(fn_name)
                if fn:
                    try:
                        fn()
                        log_activity(f"✅ Executed: {fn_name}")
                    except Exception as func_error:
                        log_error(f"❌ Function {fn_name} crashed: {func_error}")
                        log_private("⚠️ Pain signal: Function execution failed.")
                        log_pain(context, emotion="frustration", increment=0.3 + 0.3 * emotional_state.get("anger", 0.4))
                else:
                    log_model_issue(f"⚠️ Unknown function requested: {fn_name}")
            else:
                log_model_issue("⚠️ No valid function returned by think().")
                log_uncertainty_spike(context, increment=0.1 + 0.3 * emotional_state.get("uncertainty", 0.5))

            print(f"🔁 Orrin cycle {cycle_count} complete.\n")
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n🛑 Orrin loop stopped manually.")
        log_activity("Orrin loop manually interrupted by user.")

    except Exception as e:
        crash_msg = f"⚠️ Orrin crashed: {e}"
        print(crash_msg)
        traceback.print_exc()
        log_error(f"Main loop error: {e}")
        log_private("🔥 Top-level crash signal.")
        time.sleep(10)