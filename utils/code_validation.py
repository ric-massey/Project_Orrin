import tempfile
import os
import importlib.util
import traceback
import sys

def validate_think_code(code_text):
    """
    Validates that new `think()` code is safe to run.
    Checks syntax, presence of key elements, and dry run execution.
    """
    temp_path = None

    try:
        # 1. Basic syntax check
        compile(code_text, "<think_candidate>", "exec")

        # 2. Structural checks
        required_snippets = ["def think(", "update_last_active(", "return {"]
        for snippet in required_snippets:
            if snippet not in code_text:
                return False, f"❌ Missing required structure: `{snippet}`"

        # 3. Write to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as temp:
            temp.write(code_text)
            temp_path = temp.name

        # 4. Dynamically import the temp module
        module_name = os.path.splitext(os.path.basename(temp_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # Required for some dynamic imports
        spec.loader.exec_module(module)

        # 5. Check for function
        if not hasattr(module, "think"):
            return False, "❌ No `think()` function defined."

        # 6. Dry run
        result = module.think(context={})
        if not isinstance(result, dict) or "next_function" not in result:
            return False, "❌ Dry run did not return expected `dict` with `next_function`."

        return True, "✅ Passed validation."

    except SyntaxError as e:
        return False, f"❌ Syntax error: {e}"
    except Exception as e:
        return False, f"❌ Exception during validation:\n{traceback.format_exc()}"
    finally:
        # 7. Cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass