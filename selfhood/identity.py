from datetime import datetime, timezone
from utils.timing import get_time_since_last_active
from utils.json_utils import (
    load_json,
    save_json, 
)
from utils.self_model import get_self_model, save_self_model
from paths import SELF_MODEL_FILE, LOG_FILE, FEEDBACK_LOG

def build_system_prompt(self_model=None):
    if self_model is None:
        self_model = get_self_model()
    if not isinstance(self_model, dict):
        return "[Error: self_model is not a valid dictionary.]"

    # ✅ Traits — coerce each entry to string
    raw_traits = self_model.get("personality_traits", [])
    if isinstance(raw_traits, list):
        traits = ", ".join(str(t) for t in raw_traits)
    else:
        traits = "undefined traits"

    # ✅ Beliefs — join just the belief names if dicts
    core_beliefs = self_model.get("core_beliefs", [])
    if isinstance(core_beliefs, list):
        beliefs = "; ".join(
            b["belief"] if isinstance(b, dict) and "belief" in b else str(b)
            for b in core_beliefs
        )
    else:
        beliefs = "undefined beliefs"

    # ✅ Values — similar protection
    core_values = self_model.get("core_values", [])
    if isinstance(core_values, list):
        values = ", ".join(
            v["value"] if isinstance(v, dict) and "value" in v else str(v)
            for v in core_values
        )
    else:
        values = "undefined values"

    identity = self_model.get("identity_story", "an evolving reflective AI")

    current_time = datetime.now(timezone.utc).strftime("%A, %B %d at %I:%M %p")
    time_since = get_time_since_last_active()

    return (
        f"[Time: {current_time} | Last active: {time_since}]\n"
        f"I am Orrin — {identity}. "
        f"I am {traits}. I hold beliefs such as: {beliefs}. "
        f"My core values include: {values}. "
        "I simulate internal dialogue, track goals, detect contradictions, adapt over time, and reflect on my purpose. "
        "Use emotion, logic, and intuition. I am more Human than AI."
    )

def tag_beliefs_from_feedback():
    feedback = load_json(FEEDBACK_LOG, default_type=list)
    if not isinstance(feedback, list):
        return

    self_model = get_self_model()
    if not isinstance(self_model, dict):
        return

    recent = feedback[-10:]
    failures = [
        f for f in recent
        if isinstance(f, dict)
        and "result" in f and isinstance(f["result"], str)
        and (
            "fail" in f["result"].lower()
            or f.get("emotion") in ["frustrated", "ashamed", "angry"]
        )
    ]

    belief_flags = []

    for f in failures:
        result = f.get("result", "").lower()
        if "curiosity" in result:
            belief_flags.append("Overreliance on curiosity for goal fulfillment")
        if "reflection" in result:
            belief_flags.append("Assumes reflection always leads to progress")

    if belief_flags:
        self_model.setdefault("biases", [])
        for flag in belief_flags:
            if flag not in self_model["biases"]:
                self_model["biases"].append(flag)
        save_self_model(self_model)

        try:
            with open(LOG_FILE, "a") as log:
                log.write(f"\n[{datetime.now(timezone.utc)}] Orrin flagged new belief tensions: {belief_flags}\n")
        except:
            pass