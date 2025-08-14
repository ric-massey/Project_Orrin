# Minimal, strict validators for Orrin (no jsonschema dependency).
from typing import Any, Dict, List  # Optional, Union removed (unused)
import math

ToolSchema = {
    "type": "object",
    "required": ["name", "args"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "args": {"type": "object"},
        "dry_run": {"type": "boolean"},
        "timeout_s": {"type": "number", "minimum": 0, "maximum": 120}
    },
    "additionalProperties": False
}

CognitionResultSchema = {
    "type": "object",
    "required": ["kind", "status"],
    "properties": {
        "kind": {"type": "string", "enum": ["THINK", "DECISION", "ACTION", "REFLECTION"]},
        "status": {"type": "string", "enum": ["ok", "error"]},
        "message": {"type": "string"},
        "data": {"type": "object"},
        "retries": {"type": "integer", "minimum": 0}
    },
    "additionalProperties": True
}

def _is_number(x: Any) -> bool:
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x))

def _is_integer(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)

def _type_check(value, spec):
    t = spec.get("type")

    if t == "object" and not isinstance(value, dict):
        return False, f"Expected object, got {type(value).__name__}"
    if t == "string" and not isinstance(value, str):
        return False, f"Expected string, got {type(value).__name__}"
    if t == "boolean" and not isinstance(value, bool):
        return False, f"Expected boolean, got {type(value).__name__}"
    if t == "number" and not _is_number(value):
        return False, f"Expected finite number, got {repr(value)}"
    if t == "integer" and not _is_integer(value):
        return False, f"Expected integer, got {repr(value)}"
    if t == "array" and not isinstance(value, list):
        return False, f"Expected array, got {type(value).__name__}"
    if t is None:
        return True, ""

    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            return False, f"String too short (min {spec['minLength']}), got {len(value)}"
        if "enum" in spec and value not in spec["enum"]:
            return False, f"Value '{value}' not in enum {spec['enum']}"

    if _is_number(value):
        if "minimum" in spec and value < spec["minimum"]:
            return False, f"Value {value} < minimum {spec['minimum']}"
        if "maximum" in spec and value > spec["maximum"]:
            return False, f"Value {value} > maximum {spec['maximum']}"

    return True, ""

def _validate(obj: dict, schema: dict, where: str):
    ok, msg = _type_check(obj, schema)
    if not ok:
        raise ValueError(f"{where}: {msg}")

    props = schema.get("properties", {})
    required = schema.get("required", [])

    for key in required:
        if key not in obj:
            raise ValueError(f"{where}: missing required '{key}'")

    if not schema.get("additionalProperties", True):
        for k in obj.keys():
            if k not in props:
                raise ValueError(f"{where}: additional property '{k}' not allowed")

    for k, v in obj.items():
        if k in props:
            ok, msg = _type_check(v, props[k])
            if not ok:
                raise ValueError(f"{where}.{k}: {msg}")

    return obj

def validate_tool_request(obj: dict) -> dict:
    return _validate(obj, ToolSchema, "tool_request")

def validate_cognition_result(obj: dict) -> dict:
    return _validate(obj, CognitionResultSchema, "cognition_result")