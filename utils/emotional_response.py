# utils/emotional_response.py
from emotion.amygdala import process_emotional_signals
from utils.generate_response import generate_response

def generate_emotional_response(prompt, model=None, config=None):
    context = {
        "input_text": prompt,
        "mode": {"mode": "thinking"}
    }
    context, amygdala_response = process_emotional_signals(context)
    
    if amygdala_response.get("threat_detected"):
        return f"⚠️ Amygdala triggered a shortcut: {amygdala_response.get('shortcut_function')} due to {amygdala_response.get('threat_tags', [])}"

    return generate_response(prompt, model, config)