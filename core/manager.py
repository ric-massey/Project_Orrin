# manager.py
import importlib.util
import sys
from pathlib import Path
from typing import Callable, Dict

from utils.log import log_model_issue, log_private
from paths import ROOT_DIR

def load_custom_cognition() -> Dict[str, Callable]:
    """
    Dynamically load callable functions from cognition/custom_cognition/*.py.

    - Honors __all__ if present.
    - Otherwise exports all top-level callables that don't start with "_".
    - Returns {function_name: callable}. Later files override earlier names (with a warning).
    """
    directory: Path = ROOT_DIR / "cognition" / "custom_cognition"
    functions: Dict[str, Callable] = {}

    if not directory.exists():
        log_model_issue(f"[load_custom_cognition] Directory not found: {directory}")
        return functions

    # IMPORTANT: ensure this is a package for relative imports
    init_file = directory / "__init__.py"
    if not init_file.exists():
        try:
            init_file.write_text("# package marker for custom cognition\n", encoding="utf-8")
            log_private("[load_custom_cognition] Created missing __init__.py in custom_cognition/")
        except Exception as e:
            log_model_issue(f"[load_custom_cognition] Could not create __init__.py: {e}")

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix != ".py":
            continue
        if path.name.startswith("_") or path.name == "__init__.py":
            continue

        # Use the package name so relative imports work
        module_name = f"cognition.custom_cognition.{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                log_model_issue(f"[load_custom_cognition] Cannot load spec for: {path.name}")
                continue

            module = importlib.util.module_from_spec(spec)
            # Register early so intra-package relative imports can resolve
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            exported = []
            names = getattr(module, "__all__", None)
            candidates = [n for n in names if isinstance(n, str)] if isinstance(names, (list, tuple)) \
                        else [n for n in dir(module) if not n.startswith("_")]

            for name in candidates:
                obj = getattr(module, name, None)
                # If you want *only* plain functions, check types instead of callable()
                if callable(obj):
                    if name in functions and functions[name] is not obj:
                        log_model_issue(f"[load_custom_cognition] '{name}' from {path.name} overwrote previous binding.")
                    functions[name] = obj
                    exported.append(name)

            if exported:
                log_private(f"[load_custom_cognition] {path.name}: exported {', '.join(exported)}")
            else:
                log_model_issue(f"[load_custom_cognition] No callable exports found in {path.name}")

        except Exception as e:
            log_model_issue(f"[load_custom_cognition] Failed to load {path.name}: {e}")

    return functions
