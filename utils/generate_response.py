import os
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv

from utils.json_utils import load_json
from utils.coerce_to_string import coerce_to_string
from cognition.selfhood.identity import build_system_prompt
from utils.log import log_model_issue
from core.config.settings import model_roles
from paths import MODEL_CONFIG_FILE, LLM_PROMPT
from utils.self_model import get_self_model

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_thinking_model():
    return model_roles.get("thinking", "gpt-4.1")

def generate_response(prompt, model=None, config=None):
    try:
        config = config or load_json(MODEL_CONFIG_FILE, default_type=dict)
        default_key = config.get("default", "thinking")
        selected_config = config.get(default_key, {})

        if isinstance(selected_config.get("system_prompt"), (dict, list)):
            selected_config["system_prompt"] = coerce_to_string(selected_config["system_prompt"])

        model = selected_config.get("model", "gpt-4.1") if model is None else model
        temperature = selected_config.get("temperature", 0.85)
        max_tokens = selected_config.get("max_tokens", 32000)
        # --- Use get_self_model() here for the system prompt ---
        system_prompt = coerce_to_string(selected_config.get(
            "system_prompt",
            build_system_prompt(get_self_model())
        ))

        prompt = coerce_to_string(prompt)
        system_prompt = coerce_to_string(system_prompt)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        for i, msg in enumerate(messages):
            if not isinstance(msg["content"], str):
                log_model_issue(
                    f"[generate_response] ❌ messages[{i}]['content'] is not string: {type(msg['content'])} → {msg['content']}"
                )
                raise TypeError(f"OpenAI API blocked: messages[{i}]['content'] must be string")

        # === LOG PROMPT BEFORE SENDING ===
        with open(LLM_PROMPT, "a", encoding="utf-8") as f:
            f.write(f"\n\n=== {datetime.now(timezone.utc)} ===\n")
            f.write("SYSTEM PROMPT:\n" + system_prompt + "\n\n")
            f.write("USER PROMPT:\n" + prompt + "\n\n")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        reply = response.choices[0].message.content.strip()

        # === LOG THE RESPONSE ===
        with open(LLM_PROMPT, "a", encoding="utf-8") as f:
            f.write("LLM RESPONSE:\n" + reply + "\n")

        return reply

    except Exception as e:
        log_model_issue(
            f"[generate_response] API failure: {str(e)} | model: {repr(model)} | config: {repr(selected_config)}"
        )
        return None