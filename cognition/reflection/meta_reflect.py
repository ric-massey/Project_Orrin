# === Standard Library ===
import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.load_utils import load_all_known_json
from utils.log import log_error, log_private
from cognition.selfhood.self_model_conflicts import resolve_conflicts, update_self_model
from cognition.maintenance.self_modeling import self_supervised_repair
from utils.self_model import ensure_self_model_integrity, get_self_model

from paths import PRIVATE_THOUGHTS_FILE, LOG_FILE

# === Cognition Modules ===
from cognition.reflection.reflect_on_cognition import reflect_on_cognition_patterns
from cognition.repair.repair import reflect_on_cognition_rhythm
from cognition.planning.reflection import reflect_on_missed_goals, reflect_on_effectiveness
from cognition.reflection.rule_reflection import reflect_on_rules_used
from cognition.reflection.reflect_on_outcome import reflect_on_outcomes
from cognition.reflection.self_reflection import reflect_on_think
from cognition.reflection.reflect_on_self_belief import reflect_on_self_beliefs
from cognition.world_model import update_world_model


def meta_reflect(context: dict = None):
    log_private("🧠 Running meta-reflection")
    context = context or {}
    reflection_log = []
    try:
        # === Load and merge memory ===
        full_memory = load_all_known_json()
        context.update(full_memory)

        # --- Ensure self-model integrity ---
        if "self_model" in context and isinstance(context["self_model"], dict):
            context["self_model"] = ensure_self_model_integrity(context["self_model"])
        else:
            # Defensive fallback if self_model missing or invalid
            context["self_model"] = ensure_self_model_integrity(get_self_model())

        # === Context Preview ===
        if context:
            reflection_log.append("📥 Context received:")
            for k, v in context.items():
                preview = json.dumps(v, indent=2)[:300] if isinstance(v, (dict, list)) else str(v)
                reflection_log.append(f"- {k}: {preview}")

        # === Reflection Chain ===
        steps = [
            ("Cognition Patterns", reflect_on_cognition_patterns),
            ("Cognition Rhythm", reflect_on_cognition_rhythm),
            ("Missed Goals", reflect_on_missed_goals),
            ("Rules Used", reflect_on_rules_used),
            ("Outcome Review", reflect_on_outcomes),
            ("Effectiveness", reflect_on_effectiveness),
            ("World Model Update", update_world_model),
            ("Conflict Resolution", resolve_conflicts),
            ("Self-Repair", self_supervised_repair),
            ("Self-Model Update", update_self_model),
            ("Self-Beliefs", reflect_on_self_beliefs),
            ("Think Review", reflect_on_think)
        ]

        for label, func in steps:
            try:
                func()
                reflection_log.append(f"✅ {label} completed.")
            except Exception as sub_e:
                err_msg = f"⚠️ {label} failed: {sub_e}"
                log_error(err_msg)
                reflection_log.append(err_msg)

        # === Log Results ===
        now = datetime.now(timezone.utc).isoformat()
        with open(LOG_FILE, "a") as f_log:
            f_log.write(f"\n[{now}] ✅ Meta-reflection complete.\n")

        with open(PRIVATE_THOUGHTS_FILE, "a") as f_private:
            f_private.write(f"\n[{now}] 🧠 Orrin meta-reflected:\n")
            f_private.write("\n".join(reflection_log) + "\n")

        log_private("✅ Meta-reflection done.")
        return "\n".join(reflection_log)

    except Exception as e:
        error_message = f"❌ Meta-reflection failed: {e}"
        log_error(error_message)

        try:
            with open(PRIVATE_THOUGHTS_FILE, "a") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] ⚠️ Meta-reflection failed:\n{error_message}\n")
        except:
            pass

        return error_message
