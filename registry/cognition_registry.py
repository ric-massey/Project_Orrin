import os
import importlib.util
import inspect
import json
from utils.log import log_error
from utils.generate_response import generate_response
from paths import COGNITIVE_FUNCTIONS_LIST_FILE

COGNITIVE_FUNCTIONS = {}

def discover_cognitive_functions(package):
    """
    Scans all cognitive function files every time.
    Only generates summaries for new functions.
    Ensures JSON file is always up to date without re-summarizing.
    Also stores function metadata as a dict: {'function': fn, 'is_action': bool}
    """
    global COGNITIVE_FUNCTIONS

    # Load existing summaries
    try:
        with open(COGNITIVE_FUNCTIONS_LIST_FILE, "r") as f:
            existing_entries = json.load(f)
    except Exception:
        existing_entries = []

    existing_summaries = {
        entry["name"]: entry.get("summary", "")
        for entry in existing_entries
        if "name" in entry
    }

    found_functions = {}
    updated_entries = []
    base_path = package.__path__[0]

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("_") and file != "__init__.py":
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_path)
                module_name = f"{package.__name__}." + rel_path.replace(os.sep, ".").replace(".py", "")

                try:
                    spec = importlib.util.spec_from_file_location(module_name, full_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        if not name.startswith("_"):
                            # Try to detect 'is_action' from function name or docstring as a placeholder
                            is_action = False
                            doc = func.__doc__ or ""
                            if "action" in name or "@action" in doc:
                                is_action = True

                            # Store as a dict with metadata
                            COGNITIVE_FUNCTIONS[name] = {
                                "function": func,
                                "is_action": is_action
                            }
                            found_functions[name] = func

                            if name in existing_summaries:
                                summary = existing_summaries[name]
                            else:
                                try:
                                    code = inspect.getsource(func)
                                    prompt = f"Explain this Python function in one sentence:\n\n{code}\n\nSummary:"
                                    summary = generate_response(prompt).strip()
                                except Exception as e:
                                    summary = f"⚠️ Failed to summarize: {e}"

                            updated_entries.append({"name": name, "summary": summary, "is_action": is_action})

                except Exception as e:
                    log_error(f"⚠️ Failed to load {module_name}: {e}")

    # Add untouched summaries for functions that still exist
    untouched_entries = [
        {"name": name, "summary": summary, "is_action": False}
        for name, summary in existing_summaries.items()
        if name not in found_functions
    ]

    all_entries = updated_entries + untouched_entries

    # ===== DEDUPLICATE HERE =====
    deduped = {}
    for entry in all_entries:
        deduped[entry["name"]] = entry  # Overwrites previous if duplicate

    all_entries = list(deduped.values())
    all_entries = sorted(all_entries, key=lambda x: x["name"])

    try:
        with open(COGNITIVE_FUNCTIONS_LIST_FILE, "w") as f:
            json.dump(all_entries, f, indent=2)
    except Exception as e:
        log_error(f"⚠️ Failed to write cognitive functions list: {e}")