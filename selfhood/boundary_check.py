# imports
from utils.json_utils import load_json
from utils.log import log_error
from paths import RELATIONSHIPS_FILE

# == FUNCTIONS
def check_violates_boundaries(prompt):
    try:
        relationships = load_json(RELATIONSHIPS_FILE, default_type=dict)

        if not isinstance(relationships, dict):
            log_error("⚠️ RELATIONSHIPS_FILE does not contain a valid dictionary.")
            return None

        user_model = relationships.get("user", {})
        if not isinstance(user_model, dict):
            log_error("⚠️ 'user' entry in relationships is not a dictionary.")
            return None

        boundaries = user_model.get("boundaries", [])
        if not isinstance(boundaries, list):
            log_error("⚠️ 'boundaries' is not a list.")
            return None

        violations = []
        for rule in boundaries:
            if isinstance(rule, str) and rule.lower() in prompt.lower():
                violations.append(rule)

        return violations if violations else None

    except Exception as e:
        log_error(f"❌ check_violates_boundaries failed: {e}")
        return None