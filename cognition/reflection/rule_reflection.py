#imports
import json

from datetime import datetime, timezone

# === Internal Utilities ===
from utils.json_utils import (
    save_json, 
    extract_json
)
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private
from utils.log_reflection import log_reflection
from paths import (
    CASUAL_RULES,
    REF_PROMPTS,
)


def reflect_on_rules_used():
    """
    Reflects on recent memory outcomes to assess the effectiveness of Orrin's causal reasoning rules.
    Updates rules by adding, revising, or removing entries as appropriate.
    """

    all_data = load_all_known_json()
    casual_rules = all_data.get("casual_rules", {})
    long_memory = all_data.get("long_memory", [])[-15:]

    recent_outcomes = [
        m["content"]
        for m in long_memory
        if isinstance(m, dict) and "content" in m and (
            "result" in m["content"].lower() or "outcome" in m["content"].lower()
        )
    ]

    if not recent_outcomes:
        update_working_memory("No recent outcome reflections available for rule analysis.")
        return

    prompt = REF_PROMPTS.get("reflect_on_rules_used", (
        "These are my causal reasoning rules and my recent memory outcomes.\n"
        "Determine which rules were effective, need revision, or are missing.\n"
        "Use structure: {add: [...], revise: [...], remove: [...]}"
    ))

    context = {
        **all_data,
        "rules": casual_rules,
        "memory": recent_outcomes,
        "instructions": prompt
    }

    response = generate_response_from_context(context)
    rule_updates = extract_json(response)

    if not rule_updates:
        update_working_memory("Orrin reflected on rules but proposed no changes.")
        return

    updated = False

    # Add new rules
    for rule in rule_updates.get("add", []):
        domain = rule.get("domain")
        if domain and "if" in rule and "then" in rule:
            casual_rules.setdefault(domain, []).append({
                "if": rule["if"],
                "then": rule["then"]
            })
            updated = True

    # Revise existing rules
    for rule in rule_updates.get("revise", []):
        domain = rule.get("domain")
        old = rule.get("old")
        new = rule.get("new")
        if domain and old and new and domain in casual_rules:
            for i, existing_rule in enumerate(casual_rules[domain]):
                if existing_rule.get("if") == old:
                    casual_rules[domain][i]["if"] = new
                    updated = True

    # Remove outdated rules
    for rule in rule_updates.get("remove", []):
        domain = rule.get("domain")
        rule_text = rule.get("rule")
        if domain and rule_text and domain in casual_rules:
            original_len = len(casual_rules[domain])
            casual_rules[domain] = [
                r for r in casual_rules[domain] if r.get("if") != rule_text
            ]
            if len(casual_rules[domain]) < original_len:
                updated = True

    if updated:
        save_json(CASUAL_RULES, casual_rules)
        update_working_memory("Orrin updated his causal rules.")
        log_private(
            f"[{datetime.now(timezone.utc)}] Orrin reflected on his causal reasoning and made updates:\n"
            f"{json.dumps(rule_updates, indent=2)}"
        )
        log_reflection(f"Self-belief reflection: {rule_updates.strip()}")
    else:
        update_working_memory("Orrin proposed changes to rules, but none were valid or new.")

