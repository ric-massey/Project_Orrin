def generate_response_from_context(context: dict) -> str:
    try:
        from utils.core_utils import generate_response
        from utils.coerce_to_string import coerce_to_string
        from selfhood.identity import build_system_prompt
        from utils.json_utils import load_json
        from utils.log import log_model_issue
        from paths import MODEL_CONFIG_FILE
        from utils.self_model import get_self_model  # <--- import helper

        # 🧠 Step 1: Get and sanitize prompt
        instructions = context.get("instructions", "Think based on the following context.")
        prompt = coerce_to_string(instructions)

        # 🧠 Step 2: Get and sanitize system prompt
        system_prompt = context.get("system_prompt")
        if not isinstance(system_prompt, str):
            try:
                system_prompt = build_system_prompt(get_self_model())
            except Exception as e:
                log_model_issue(f"[generate_response_from_context] Failed to build system prompt: {str(e)}")
                system_prompt = "You are a thoughtful, reflective intelligence."

        system_prompt = coerce_to_string(system_prompt)

        # 🧠 Step 3: Load full model config
        config = load_json(MODEL_CONFIG_FILE, default_type=dict)
        default_key = config.get("default", "thinking")
        selected_config = config.get(default_key, {}).copy()

        if not isinstance(selected_config, dict):
            selected_config = {}

        # 🧹 Inject coerced system_prompt
        selected_config["system_prompt"] = system_prompt

        # ✅ Final generate call with sanitized prompt + config
        return generate_response(prompt, config=selected_config)

    except Exception as e:
        from utils.log import log_model_issue
        log_model_issue(f"[generate_response_from_context] Failed: {str(e)}")
        return "⚠️ Failed to generate a response from context."