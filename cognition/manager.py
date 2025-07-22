# == Imports
import os
import importlib.util

from utils.log import log_model_issue, log_private


# == Function
def load_custom_cognition():
    directory = os.path.abspath("custom_cognition")
    functions = {}

    if not os.path.exists(directory):
        log_model_issue(f"[load_custom_cognition] Directory not found: {directory}")
        return functions

    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            filepath = os.path.join(directory, filename)
            module_name = filename[:-3]

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec is None or spec.loader is None:
                    log_model_issue(f"[load_custom_cognition] Cannot load spec for: {filename}")
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, module_name):
                    functions[module_name] = getattr(module, module_name)
                    log_private(f"[load_custom_cognition] Successfully loaded: {module_name}")
                else:
                    log_model_issue(f"[load_custom_cognition] No function '{module_name}' in {filename}")

            except Exception as e:
                log_model_issue(f"[load_custom_cognition] Failed to load {filename}: {e}")

    return functions