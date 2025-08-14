
from utils.json_utils import load_json
from utils.log import log_error
from paths import RELATIONSHIPS_FILE

def check_violates_boundaries(prompt):
    """
    Return a list of boundary rules that the prompt appears to violate.
    Returns [] when no violations are found, and None only on hard failure.
    Supports string rules (substring match). If a rule dict has {"regex": "..."},
    it will be applied as a regex.
    """
    import re

    try:
        relationships = load_json(RELATIONSHIPS_FILE, default_type=dict)
        if not isinstance(relationships, dict):
            log_error("⚠️ RELATIONSHIPS_FILE is not a dict.")
            return None

        user_model = relationships.get("user", {})
        if not isinstance(user_model, dict):
            log_error("⚠️ 'user' in relationships is not a dict.")
            return None

        boundaries = user_model.get("boundaries", [])
        if not isinstance(boundaries, list):
            log_error("⚠️ 'boundaries' is not a list.")
            return None

        text = str(prompt or "")
        text_l = text.lower()
        violations = []

        for rule in boundaries:
            if isinstance(rule, str):
                if rule.lower() in text_l:
                    violations.append(rule)
            elif isinstance(rule, dict):
                pat = rule.get("regex")
                name = rule.get("name", pat)
                if pat:
                    try:
                        if re.search(pat, text, flags=re.IGNORECASE):
                            violations.append(name or pat)
                    except re.error as e:
                        log_error(f"⚠️ Bad boundary regex '{pat}': {e}")

        return violations  # empty list means no violations

    except Exception as e:
        log_error(f"❌ check_violates_boundaries failed: {e}")
        return None