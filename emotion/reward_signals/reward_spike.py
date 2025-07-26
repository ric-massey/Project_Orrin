from datetime import datetime, timezone
from utils.log import log_private
import random

def log_reward_spike(signal_type="dopamine", strength=1.0, tags=None):
    timestamp = datetime.now(timezone.utc).isoformat()
    tags = tags or []

    # Humanlike phrasing variations
    phrases = [
        "A noticeable surge of",
        "An unexpected rise in",
        "A clear spike in",
        "A subtle increase of",
        "A strong wave of",
        "A sudden boost in",
        "A marked increase in",
    ]
    phrase = random.choice(phrases)

    # Qualitative description of strength
    if strength > 0.8:
        intensity = "intense"
    elif strength > 0.5:
        intensity = "strong"
    elif strength > 0.2:
        intensity = "moderate"
    else:
        intensity = "slight"

    # Compose the log message
    message = (
        f"{phrase} {signal_type} detected "
        f"({intensity} signal, strength {strength:.2f})."
    )

    # Add tags if any
    if tags:
        message += f" Tags observed: {', '.join(tags)}."

    # Reflective humanlike comment for context
    reflections = {
        "dopamine": "This suggests rising motivation and confidence.",
        "novelty": "Curiosity seems to have been triggered by something new.",
        "serotonin": "Indications of improved emotional stability.",
        "connection": "Strengthening of social or emotional bonds detected.",
        "reward_impulse": "An impulse has been triggered, prompting action.",
    }
    reflection = reflections.get(signal_type.lower())
    if reflection:
        message += " " + reflection

    log_private(f"[{timestamp}] {message}")