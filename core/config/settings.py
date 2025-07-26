from utils.load_utils import load_model_config
from utils.log import log_error  # optional: for diagnostic logging

model_roles = load_model_config()

# Ensure model_roles is a dict
if not isinstance(model_roles, dict):
    log_error("⚠️ load_model_config() returned a non-dict. Defaulting to empty config.")
    model_roles = {}

# Set defaults safely - for now im runnint gpt-4.1 for both because it is cheaper
model_roles.setdefault("thinking", "gpt-4.1")
model_roles.setdefault("human_facing", "gpt-4.1")