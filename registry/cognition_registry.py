import os
import importlib.util
import inspect
from utils.log import log_error

COGNITIVE_FUNCTIONS = {}
_last_mtime_map = {}

def discover_cognitive_functions(package):
    """
    Discovers and loads all callable cognitive functions from the given package.
    Only refreshes if source files have changed.
    """
    global COGNITIVE_FUNCTIONS, _last_mtime_map

    base_path = package.__path__[0]
    updated_mtime_map = {}
    files_to_reload = []

    # Check for changes
    for root, _, files in os.walk(base_path):
        for file in files:
            if (
                file.endswith(".py")
                and not file.startswith("_")
                and file != "__init__.py"
            ):
                full_path = os.path.join(root, file)
                mtime = os.path.getmtime(full_path)
                updated_mtime_map[full_path] = mtime

                if _last_mtime_map.get(full_path) != mtime:
                    files_to_reload.append(full_path)

    if not files_to_reload:
        return  # No changes detected

    # Refresh functions
    COGNITIVE_FUNCTIONS = {}

    for full_path in files_to_reload:
        rel_path = os.path.relpath(full_path, base_path)
        module_name = f"{package.__name__}." + rel_path.replace(os.sep, ".").replace(".py", "")

        try:
            spec = importlib.util.spec_from_file_location(module_name, full_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name, func in inspect.getmembers(module, inspect.isfunction):
                if not name.startswith("_"):
                    COGNITIVE_FUNCTIONS[name] = func

        except Exception as e:
            log_error(f"⚠️ Failed to load {module_name}: {e}")

    _last_mtime_map = updated_mtime_map