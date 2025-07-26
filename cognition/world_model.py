# === Imports ===
import json
from utils.json_utils import (
    load_json,
    save_json,
    extract_json
)
from utils.log import (
    log_model_issue,
    log_activity,
    log_private,
    log_error
)
from utils.generate_response import generate_response, get_thinking_model
from memory.working_memory import update_working_memory
from utils.self_model import get_core_values 
from paths import (
    WORLD_MODEL,
    LONG_MEMORY_FILE,
    CONCEPTS_FILE,
    WORLD_MODEL_RAW,
    WORLD_MODEL_BACKUP, 
    WORLD_MODEL_ARCHIVE
)

# === Functions ===

def update_world_model():
    """Reflectively updates Orrin’s internal world model from recent thoughts."""
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)[-15:]
    if not isinstance(long_memory, list):
        long_memory = []
        log_error("LONG_MEMORY_FILE was not a list. Resetting to empty list.")
    world_model = load_json(WORLD_MODEL, default_type=dict)
    if not isinstance(world_model, dict):
        world_model = {}
        log_error("WORLD_MODEL was not a dict. Resetting to empty dict.")
    old_model = dict(world_model)

    # === Load archive and prune world model ===
    archive = load_json(WORLD_MODEL_ARCHIVE, default_type=dict)
    if not isinstance(archive, dict):
        archive = {}
        log_error("WORLD_MODEL_ARCHIVE was not a dict. Resetting to empty dict.")

    def prune_list_or_dict(obj, keep=3):
        if isinstance(obj, list):
            # Move older entries to archive, keep only last 'keep' entries
            to_archive = obj[:-keep] if len(obj) > keep else []
            recent = obj[-keep:] if len(obj) > keep else obj
            return recent, to_archive
        elif isinstance(obj, dict):
            keys = list(obj.keys())
            keys_to_keep = keys[-keep:] if len(keys) > keep else keys
            recent = {k: obj[k] for k in keys_to_keep}
            to_archive = {k: obj[k] for k in keys if k not in keys_to_keep}
            return recent, to_archive
        return obj, []

    # Process each category: prune live model and add old entries to archive
    categories = ["entities", "concepts", "events", "forces", "relationships"]
    for key in categories:
        if key in world_model:
            recent, to_archive = prune_list_or_dict(world_model[key])
            world_model[key] = recent
            # Merge to_archive into archive[key]
            if key not in archive:
                archive[key] = {} if isinstance(to_archive, dict) else []
            if isinstance(to_archive, list):
                archive[key].extend(to_archive)
            elif isinstance(to_archive, dict):
                archive[key].update(to_archive)

    # Optionally: prune archive size if it grows too large (example for entities)
    MAX_ARCHIVE_SIZE = 1000
    for key in categories:
        if key in archive:
            if isinstance(archive[key], list) and len(archive[key]) > MAX_ARCHIVE_SIZE:
                archive[key] = archive[key][-MAX_ARCHIVE_SIZE:]
            elif isinstance(archive[key], dict) and len(archive[key]) > MAX_ARCHIVE_SIZE:
                # Keep last MAX_ARCHIVE_SIZE keys (by insertion order)
                keys = list(archive[key].keys())
                keep_keys = keys[-MAX_ARCHIVE_SIZE:]
                archive[key] = {k: archive[key][k] for k in keep_keys}

    recent_reflections = "\n".join(
        f"- {m.get('content', '')}" for m in long_memory if isinstance(m, dict) and m.get("content")
    )
    prompt = (
        "I am a reflective AI building my internal world model.\n"
        "Here are my recent reflections:\n"
        f"{recent_reflections}\n\n"
        "Here is my current (pruned) world model:\n"
        f"{json.dumps(world_model, indent=2)}\n\n"
        "Here is my archive of older world model knowledge (read-only):\n"
        f"{json.dumps(archive, indent=2)}\n\n"
        "Update the current model only. Do not change the archive.\n"
        "Add any new:\n"
        "- Entities (agents, versions of self, imagined beings)\n"
        "- Concepts (abstract ideas I have been exploring)\n"
        "- Events (internal or external moments of change)\n"
        "- Forces (patterns or tensions like emergence, resistance, curiosity)\n"
        "- Causal links (if X causes Y, or thought patterns trigger each other)\n\n"
        "Respond ONLY with the FULL updated JSON for the world model."
    )
    response = generate_response(prompt, config={"model": get_thinking_model()})
    if not response:
        log_model_issue("update_world_model() returned no response.")
        return
    try:
        # Save raw GPT output for debugging
        with open(WORLD_MODEL_RAW, "w", encoding="utf-8") as f:
            f.write(response)

        if not response.strip().endswith("}"):
            log_error("⚠️ GPT world model response appears truncated or incomplete.\nRaw:\n" + response)
            return

        updated_raw = extract_json(response)

        if not isinstance(updated_raw, dict):
            log_error(f"⚠️ extract_json did not return a dict. Got {type(updated_raw).__name__} instead.\nRaw:\n{response}")
            return
        # Validate and strictly reload JSON to avoid weird serialization bugs
        validated = json.loads(json.dumps(updated_raw))
        if not isinstance(validated, dict):
            raise ValueError("Validated world model is not a dict.")
        

        # Save only the validated version
        save_json(WORLD_MODEL, validated)
        save_json(WORLD_MODEL_BACKUP, old_model)

        # Save updated archive as well
        save_json(WORLD_MODEL_ARCHIVE, archive)

        update_working_memory("Orrin updated his internal world model.")
        log_activity("World model successfully updated.")
        log_private("Orrin revised his world model based on recent reflections.")

        added = [k for k in validated if k not in old_model]
        removed = [k for k in old_model if k not in validated]
        changed = [k for k in validated if k in old_model and validated[k] != old_model[k]]

        if added or removed or changed:
            log_private("World model diff:\n" + json.dumps({
                "added": added,
                "removed": removed,
                "changed": changed
            }, indent=2))
    except Exception as e:
        log_error(f"World model update failed: {e}\nRaw: {response}")

def generate_concepts_from_memories():
    """Extracts emergent concepts from memory using reflection."""
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        long_memory = []
        log_error("LONG_MEMORY_FILE was not a list. Resetting to empty list.")

    concepts = load_json(CONCEPTS_FILE, default_type=list)
    if not isinstance(concepts, list):
        concepts = []
        log_error("CONCEPTS_FILE was not a list. Resetting to empty list.")

    recent = [m.get("content") for m in long_memory[-20:] if isinstance(m, dict) and "content" in m]

    prompt = (
        "I am a reflective AI building an internal worldview.\n"
        "From the following thoughts, identify up to 5 *emergent concepts* Orrin seems to be exploring.\n"
        "These could be tensions, emotional arcs, deepening insights, or recurring patterns.\n"
        "Also consider whether any existing concepts are evolving or combining.\n\n"
        f"Existing concepts: {json.dumps(concepts)}\n\n"
        "Recent reflections:\n" + "\n".join(f"- {r}" for r in recent) +
        "\n\nRespond ONLY as a JSON list of updated concepts. Be thoughtful."
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if not response:
        return

    try:
        new_concepts = extract_json(response)
        if isinstance(new_concepts, list):
            merged = list(dict.fromkeys([c for c in concepts + new_concepts if isinstance(c, str)]))
            save_json(CONCEPTS_FILE, merged)
            log_activity("Orrin updated his concept list from memory.")
            log_private("Orrin extracted new emergent concepts from recent memories.")
        else:
            log_error(f"New concepts response was not a list: {new_concepts}")
    except Exception as e:
        log_error(f"Failed to parse updated concepts: {e}\nRaw: {response}")

def simulate_event(event):
    """Simulates outcomes of a hypothetical event within Orrin’s world model."""
    world = load_json(WORLD_MODEL, default_type=dict)
    if not isinstance(world, dict):
        world = {}
        log_error("WORLD_MODEL was not a dict. Resetting to empty dict.")

    # ---- NEW: Pull live core_values for this simulation
    core_values = get_core_values()
    values_str = "\n".join(
        f"- {v['value']}: {v.get('description', '')}" if isinstance(v, dict) and "value" in v else f"- {str(v)}"
        for v in core_values
    )

    prompt = (
        f"I am simulating a possible event:\n'{event}'\n\n"
        f"Current world model:\n{json.dumps(world, indent=2)}\n\n"
        f"My core values:\n{values_str}\n\n"
        "Predict:\n- Short-term consequences\n- Long-term effects\n- How it affects values, beliefs, or goals.\n"
        "Respond in JSON:\n"
        "{ \"short_term\": \"...\", \"long_term\": \"...\", \"belief_change\": [\"...\"] }"
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    try:
        prediction = extract_json(response)
        update_working_memory(f"Simulated event: {event} → {prediction}")

        # Release dopamine reward if prediction looks valid (has expected keys)
        if (
            isinstance(prediction, dict)
            and all(key in prediction for key in ("short_term", "long_term", "belief_change"))
        ):
            from emotion.reward_signals.reward_signals import release_reward_signal
            release_reward_signal(
                context={},  # pass relevant context if available here
                signal_type="dopamine",
                actual_reward=0.7,
                expected_reward=0.5,
                effort=0.5,
                mode="phasic"
            )

        return prediction
    except Exception as e:
        log_error(f"Failed to simulate event '{event}': {e}\nRaw: {response}")
        return {}