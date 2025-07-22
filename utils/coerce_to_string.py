def coerce_to_string(value):
    if isinstance(value, dict):
        return "\n\n".join(f"→ {k.replace('_', ' ').title()}:\n{coerce_to_string(v)}" for k, v in value.items())
    elif isinstance(value, list):
        return "\n".join(coerce_to_string(v) for v in value)
    elif not isinstance(value, str):
        return str(value)
    return value
