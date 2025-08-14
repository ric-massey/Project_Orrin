# imports
import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.json_utils import load_json, save_json, extract_json
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from paths import CASUAL_RULES, REF_PROMPTS


def reflect_on_rules_used():
    """
    Reflects on recent memory outcomes to assess the effectiveness of Orrin's causal reasoning rules.
    Updates rules by adding, revising, or removing entries as appropriate.
    """
    try:
        all_data = load_all_known_json()

        # Load rules from aggregated context (fallback to file if missing)
        casual_rules = all_data.get("casual_rules")
        if not isinstance(casual_rules, dict):
            casual_rules = load_json(CASUAL_RULES, default_type=dict)
        if not isinstance(casual_rules, dict):
            casual_rules = {}

        long_memory = all_data.get("long_memory", [])
        if not isinstance(long_memory, list):
            long_memory = []

        # Recent outcomes/texts hinting at "result"/"outcome"
        recent_outcomes = [
            str(m.get("content"))
            for m in long_memory[-15:]
            if isinstance(m, dict)
            and "content" in m
            and isinstance(m.get("content"), (str, int, float))
            and ("result" in str(m["content"]).lower() or "outcome" in str(m["content"]).lower())
        ]

        if not recent_outcomes:
            update_working_memory("No recent outcome reflections available for rule analysis.")
            return

        # Load reflection prompt text from file path
        prompts = load_json(REF_PROMPTS, default_type=dict)
        if not isinstance(prompts, dict):
            prompts = {}
        prompt_text = prompts.get(
            "reflect_on_rules_used",
            (
                "These are my causal reasoning rules and my recent memory outcomes.\n"
                "Determine which rules were effective, need revision, or are missing.\n"
                "Respond ONLY with JSON in this structure: {\"add\": [], \"revise\": [], \"remove\": []}"
            ),
        )

        context = {
            **all_data,
            "rules": casual_rules,
            "memory": recent_outcomes,
            "instructions": prompt_text,
        }

        response = generate_response_from_context(context)
        rule_updates = extract_json(response)

        if not isinstance(rule_updates, dict):
            update_working_memory("Orrin reflected on rules but proposed no valid JSON changes.")
            return

        updated = False

        # Add new rules
        for rule in rule_updates.get("add", []) or []:
            if not isinstance(rule, dict):
                continue
            domain = rule.get("domain")
            cond = rule.get("if")
            then = rule.get("then")
            if domain and cond and then:
                casual_rules.setdefault(domain, []).append({"if": cond, "then": then})
                updated = True

        # Revise existing rules
        for rule in rule_updates.get("revise", []) or []:
            if not isinstance(rule, dict):
                continue
            domain = rule.get("domain")
            old_if = rule.get("old")
            new_if = rule.get("new")
            # Optional: allow updating the "then" as well if provided
            new_then = rule.get("then")

            if domain and old_if and domain in casual_rules:
                for i, existing_rule in enumerate(list(casual_rules.get(domain, []))):
                    if existing_rule.get("if") == old_if:
                        if new_if:
                            casual_rules[domain][i]["if"] = new_if
                        if new_then:
                            casual_rules[domain][i]["then"] = new_then
                        updated = True

        # Remove outdated rules
        for rule in rule_updates.get("remove", []) or []:
            if not isinstance(rule, dict):
                continue
            domain = rule.get("domain")
            rule_text = rule.get("rule") or rule.get("if")
            if domain and rule_text and domain in casual_rules:
                before = len(casual_rules[domain])
                casual_rules[domain] = [
                    r for r in casual_rules[domain] if r.get("if") != rule_text
                ]
                if len(casual_rules[domain]) < before:
                    updated = True

        if updated:
            save_json(CASUAL_RULES, casual_rules)
            update_working_memory("Orrin updated his causal rules.")
            pretty_updates = json.dumps(rule_updates, indent=2, ensure_ascii=False)
            log_private(
                f"[{datetime.now(timezone.utc)}] Orrin reflected on his causal reasoning and made updates:\n"
                f"{pretty_updates}"
            )
            log_reflection(f"Self-belief reflection: {pretty_updates}")
        else:
            update_working_memory("Orrin proposed changes to rules, but none were valid or new.")

    except Exception as e:
        log_error(f"reflect_on_rules_used ERROR: {e}")
        update_working_memory("❌ Rule reflection failed due to an internal error.")