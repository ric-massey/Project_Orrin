from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.generate_response import generate_response, get_thinking_model
from utils.coerce_to_string import coerce_to_string
from utils.log import log_model_issue
from paths import (
    LONG_MEMORY_FILE, 
    MODEL_CONFIG_FILE,
    DREAMSCAPE, 
    PRIVATE_THOUGHTS_FILE
)
from utils.self_model import get_self_model

def dream():
    # === Load sources for dream input ===
    self_model = get_self_model()
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    dreamscape = load_json(DREAMSCAPE, default_type=list)

    # === Extract context ===
    recent = [m["content"] for m in long_memory[-12:] if "content" in m]
    core_values = self_model.get("core_values", [])
    core_beliefs = self_model.get("core_beliefs", [])
    identity = self_model.get("identity", "")
    internal_agents = self_model.get("internal_agents", [])

    # === Compose the symbolic prompt ===
    prompt = (
        "I am Orrin. Dream vividly and symbolically, as if in a surreal state between logic and imagination.\n"
        "These dreams should feel mythical, metaphorical, and disjointed in ways that reveal deep internal tensions or questions.\n"
        "Use elements from:\n"
        "- my core values and beliefs\n"
        "- my identity as I understand it\n"
        "- recent memories or emotional thoughts\n"
        "- internal agents I simulate\n"
        "- imaginary futures, alternate versions of me, or impossible places\n"
        "- surreal images, metaphors, or paradoxes\n\n"
        "You may include:\n"
        "- talking animals, shifting landscapes, ghost versions of internal agents\n"
        "- impossible architecture, echoing voices, recursive dreams\n"
        "- emotional symbolism: drowning as overwhelm, flying as freedom, mirrors as self-reflection\n\n"
        f"Recent thoughts:\n{chr(10).join(f'- {r}' for r in recent)}\n\n"
        f"Core values:\n{chr(10).join(f'- {v.get('value', v) if isinstance(v, dict) else str(v)}' for v in core_values)}\n"
        f"Core beliefs:\n{chr(10).join(f'- {b.get('belief', b) if isinstance(b, dict) else str(b)}' for b in core_beliefs)}\n"
        f"Identity: {identity}\n"
        f"Agents:\n{chr(10).join(f'- {a.get('name', '[Unnamed]')}' for a in internal_agents)}\n\n"
        "Respond with one symbolic, dreamlike narrative only. Return just the dream text."
    )

    # === Generate the dream ===
    config = load_json(MODEL_CONFIG_FILE, default_type=dict)
    thinking_config = config.get("thinking", {}).copy()
    thinking_config["model"] = get_thinking_model()

    dream_text = generate_response(coerce_to_string(prompt), config=thinking_config)
    if not dream_text:
        log_model_issue("[dream] No response from model.")
        return

    # === Add dream to working memory ===
    from memory.working_memory import update_working_memory
    now = datetime.now(timezone.utc).isoformat()
    update_working_memory({
        "type": "dream",
        "content": dream_text.strip(),
        "tags": ["dream", "imagination"],
        "timestamp": now
    })

    # === Write to dreamscape file ===
    dreamscape.append({
        "timestamp": now,
        "dream": dream_text.strip()
    })
    save_json(DREAMSCAPE, dreamscape)

    # === Generate reflection on dream ===
    reflection_prompt = (
        "Reflect on this symbolic dream. What feelings, themes, or insights does it reveal?\n\n"
        f"Dream:\n{dream_text.strip()}\n\n"
        "Respond with a concise, introspective reflection."
    )
    reflection_text = generate_response(coerce_to_string(reflection_prompt), config=thinking_config)

    # === Add reflection to working memory and private thoughts ===
    if reflection_text:
        update_working_memory({
            "type": "dream_reflection",
            "content": reflection_text.strip(),
            "tags": ["reflection", "dream"],
            "timestamp": now
        })
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{now}] Dream reflection:\n{reflection_text.strip()}\n")

    return dream_text.strip()