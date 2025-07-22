import os
import importlib.util
import inspect
from utils.log import log_error

def discover_cognitive_functions(package):
    base_path = package.__path__[0]
    cognitive_functions = {}

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("_"):
                module_path = os.path.join(root, file)
                rel_path = os.path.relpath(module_path, base_path)
                module_name = f"{package.__name__}." + rel_path.replace(os.sep, ".").replace(".py", "")

                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        if not name.startswith("_"):
                            cognitive_functions[name] = func
                except Exception as e:
                    log_error(f"⚠️ Failed to load {module_name}: {e}")

    return cognitive_functions