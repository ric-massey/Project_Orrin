# utils/signal_utils.py

import random
from datetime import datetime, timezone

def create_signal(source, content, signal_strength=0.5, tags=None, novelty=0.0):
    """
    Creates a standardized signal dictionary.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "content": content,
        "signal_strength": signal_strength,
        "tags": tags or [],
        "novelty": novelty
    }

def gather_signals(context):
    """
    Mocked signal collection from Orrin's subsystems.
    You can later hook this into real sensors, memory, emotion, etc.
    """
    signals = []

    # Working memory check
    if not context.get("working_memory"):
        signals.append(create_signal(
            source="working_memory",
            content="Working memory is empty.",
            signal_strength=0.3,
            tags=["confusion", "low_data"],
            novelty=0.4
        ))

    # Long memory check
    if not context.get("long_memory"):
        signals.append(create_signal(
            source="long_memory",
            content="Long-term memory is missing.",
            signal_strength=0.4,
            tags=["anxiety", "uncertainty"],
            novelty=0.5
        ))

    # Emotional spikes
    emotional_state = context.get("emotional_state", {})
    for emotion, value in emotional_state.items():
        if value > 0.6:
            signals.append(create_signal(
                source="emotion",
                content=f"Emotion '{emotion}' is elevated at {value}.",
                signal_strength=value,
                tags=["emotion", emotion],
                novelty=random.uniform(0.1, 0.6)
            ))

    return signals