import os
import time
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv
import openai

from think.think_module import think
from cognition.manager import load_custom_cognition
from emotion.emotion import update_emotional_state, reflect_on_emotions
from cognition.planning.reflection import record_decision
from emotion.emotion_drift import check_emotion_drift

from utils.load_utils import load_context
from utils.json_utils import load_json
from utils.log import log_error, log_private, log_activity, log_model_issue
from utils.emotion_utils import log_pain, log_uncertainty_spike
from registry.cognition_registry import discover_cognitive_functions, COGNITIVE_FUNCTIONS
from think.thalamus import process_inputs

from paths import RELATIONSHIPS_FILE, MODEL_CONFIG_FILE

# === Init Directories ===
for path in [RELATIONSHIPS_FILE, MODEL_CONFIG_FILE]:
    path.parent.mkdir(parents=True, exist_ok=True)

# === Load OpenAI API Key ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise EnvironmentError("❌ OPENAI_API_KEY not found. Please set it in your .env file.")

# === Load Model Config ===
model_config = load_json(MODEL_CONFIG_FILE, default_type=dict)
selected = model_config.get(model_config.get("default", "thinking"), {})
model_name = selected.get("model", "gpt-4.1")
temperature = selected.get("temperature", 0.7)
max_tokens = selected.get("max_tokens", 32000)
system_prompt = selected.get("system_prompt", "")

# === Load Cognitive Functions ===
try:
    print("loading cognition files....")
    import cognition
    discover_cognitive_functions(cognition)
    COGNITIVE_FUNCTIONS.update(load_custom_cognition())
    print("discovered all cognition functions")
except Exception as e:
    log_error(f"⚠️ Failed to load cognitive functions: {e}")

# === Main Runtime Loop ===
if __name__ == "__main__":
    while True:
        try:
            print("thinking....")
            timestamp = datetime.now(timezone.utc).isoformat()
            log_activity(f"🫀 Starting cycle at {timestamp}")

            update_emotional_state()
            context = load_context()
            emotional_state = context.get("emotional_state", {})

            # === Reflex Layer ===
            if emotional_state.get("emotional_stability", 1.0) < 0.6:
                reflect_on_emotions(context, context.get("self_model", {}), context.get("long_memory", []))
            if not context.get("working_memory"):
                log_pain(context, "confusion", increment=0.2 + 0.3 * (1.0 - emotional_state.get("confidence", 0.5)))
            if not context.get("long_memory"):
                log_pain(context, "anxiety", increment=0.15 + 0.2 * emotional_state.get("uncertainty", 0.5))

            # === Thalamus: Signal Processing ===
            raw_signals = context.get("raw_signals", [])
            top_signals, attention_mode = process_inputs(raw_signals, context)
            context["top_signals"] = top_signals
            context["attention_mode"] = attention_mode

            # === Cortical Layer ===
            result = think(context)

            if isinstance(result, dict):
                from think.think_utils.action_gate import take_action
                speaker = context.get("speaker")
                
                # === Immediate Motor Output ===
                if "action" in result:
                    try:
                        take_action(result["action"], context, speaker)
                        log_activity(f"🎤 Action Taken: {result['action']['type']}")
                        continue  # Skip function selection if action occurred
                    except Exception as e:
                        log_error(f"❌ Action execution failed: {e}")
                        log_pain(context, "frustration", increment=0.3)

                # === Function-Based Thinking ===
                if "next_function" in result:
                    fn_name = result["next_function"]
                    record_decision(fn_name, result.get("reason", "No reason given."))
                    check_emotion_drift(max_cycles=10)
                    fn = COGNITIVE_FUNCTIONS.get(fn_name)
                    if fn:
                        try:
                            fn()
                            log_activity(f"✅ Executed: {fn_name}")
                        except Exception as e:
                            log_error(f"❌ Function {fn_name} crashed: {e}")
                            log_private("⚠️ Pain signal: Function execution failed.")
                            log_pain(context, "frustration", increment=0.3 + 0.3 * emotional_state.get("anger", 0.4))
                    else:
                        log_model_issue(f"⚠️ Unknown function requested: {fn_name}")
                else:
                    log_model_issue("⚠️ No valid instruction returned by think().")
                    log_uncertainty_spike(context, increment=0.1)

            print("🔁 Orrin cycle complete.\n")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\n🛑 Orrin loop stopped manually.")
            log_activity("Orrin loop manually interrupted by user.")
            break

        except Exception as e:
            print(f"⚠️ Orrin crashed: {e}")
            traceback.print_exc()
            log_error(f"Main loop error: {e}")
            log_private("🔥 Top-level crash signal.")
            time.sleep(10)