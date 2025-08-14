import tempfile
import os
import importlib.util
import traceback
import sys
import ast
from types import ModuleType
from typing import Tuple

def validate_think_code(code_text: str) -> Tuple[bool, str]:
    """
    Validates candidate code for a `think(context)` function:
    - Syntax check
    - Structural check (a function named `think` accepting at least 1 arg)
    - Dynamic import
    - Dry-run invocation with a minimal context
    Returns (ok, message).
    """
    temp_path = None
    module_name = None

    try:
        # 1) Syntax & AST structure
        tree = ast.parse(code_text, filename="<think_candidate>", mode="exec")
        has_think = False
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "think":
                # must accept at least 1 parameter (context)
                if len(node.args.args) < 1:
                    return False, "❌ `think` must accept at least one argument (context)."
                has_think = True
                break
        if not has_think:
            return False, "❌ No `think(context)` function defined."

        # 2) Write to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tmp:
            tmp.write(code_text)
            temp_path = tmp.name

        # 3) Dynamic import
        module_name = os.path.splitext(os.path.basename(temp_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        if spec is None or spec.loader is None:
            return False, "❌ Failed to build import spec for candidate module."
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # may raise

        # 4) Presence of think
        think_fn = getattr(module, "think", None)
        if not callable(think_fn):
            return False, "❌ No callable `think` found after import."

        # 5) Dry run (use a minimal context that won’t explode on key lookups)
        minimal_context = {
            "cycle_count": {"count": 0},
            "working_memory": [],
            "long_memory": [],
            "relationships": {},
            "emotional_state": {},
        }
        result = think_fn(minimal_context)

        # 6) Validate return shape
        if not isinstance(result, dict):
            return False, "❌ Dry run must return a dict."
        if "next_function" not in result and "action" not in result:
            return False, "❌ Expected `next_function` or `action` in result dict."

        return True, "✅ Passed validation."

    except SyntaxError as e:
        return False, f"❌ Syntax error: {e}"
    except Exception:
        return False, f"❌ Exception during validation:\n{traceback.format_exc()}"
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        # Remove temp module from sys.modules so future imports don’t collide
        if module_name and module_name in sys.modules:
            try:
                del sys.modules[module_name]
            except Exception:
                pass