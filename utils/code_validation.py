

def validate_think_code(code_text):
    """
    Validates that new `think()` code is safe to run.
    Checks syntax, presence of key elements, and dry run execution.
    """
    import tempfile
    import os
    import importlib.util
    import traceback

    temp_path = None

    try:
        # 1. Basic syntax test
        compile(code_text, "<think_candidate>", "exec")

        # 2. Check required parts
        required_snippets = ["def think(", "update_last_active(", "return {"]
        for snippet in required_snippets:
            if snippet not in code_text:
                return False, f"Missing required structure: {snippet}"

        # 3. Dry run test in a sandbox
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp:
            temp.write(code_text.encode())
            temp_path = temp.name

        spec = importlib.util.spec_from_file_location("think_test", temp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "think"):
            return False, "No `think()` function defined."

        # 4. Run dry with fake context
        result = module.think(context={})
        if not isinstance(result, dict) or "next_function" not in result:
            return False, "Dry run did not return expected output structure."

        return True, "✅ Passed validation."

    except SyntaxError as e:
        return False, f"❌ Syntax error: {e}"
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"❌ Exception during validation: {e}\n{tb}"
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass