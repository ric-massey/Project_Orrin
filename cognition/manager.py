import os
from utils.log import log_model_issue, log_private
import importlib



def load_custom_cognition():
    directory = os.path.abspath("custom_cognition")
    functions = {}

    if not os.path.exists(directory):
        log_model_issue(f"[load_custom_cognition] Directory not found: {directory}")
        return functions

    for filename in os.listdir(directory):
        if not filename.endswith(".py") or filename.startswith("_") or filename == "__init__.py":
            continue

        filepath = os.path.join(directory, filename)
        module_name = filename[:-3]

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                log_model_issue(f"[load_custom_cognition] Cannot load spec for: {filename}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            found = False
            for name in dir(module):
                obj = getattr(module, name)
                if callable(obj) and not name.startswith("_"):
                    functions[name] = obj
                    found = True
                    log_private(f"[load_custom_cognition] Loaded function '{name}' from {filename}")

            if not found:
                log_model_issue(f"[load_custom_cognition] No callable functions found in {filename}")

        except Exception as e:
            log_model_issue(f"[load_custom_cognition] Failed to load {filename}: {e}")

    return functions