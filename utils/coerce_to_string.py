def coerce_to_string(value, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        return "\n\n".join(
            f"{pad}→ {str(k).replace('_', ' ').title()}:\n{coerce_to_string(v, indent + 1)}"
            for k, v in value.items()
        )
    elif isinstance(value, list):
        return "\n".join(coerce_to_string(v, indent) for v in value)
    elif not isinstance(value, str):
        return pad + str(value)
    return pad + value