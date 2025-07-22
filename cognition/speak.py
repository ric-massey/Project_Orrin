import time
import json
import random
import re
from utils.log import log_private, log_activity, log_error
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import load_json, save_json
from paths import (
    PRIVATE_THOUGHTS_FILE, 
    LONG_MEMORY_FILE,
    SPEAKER_STATE_FILE
)

class OrrinSpeaker:
    def __init__(self, self_model, long_memory=None):
        # --- Ensure self_model is always a dict (even if passed as JSON string) ---
        if isinstance(self_model, str):
            try:
                self_model = json.loads(self_model)
            except Exception:
                raise ValueError(f"OrrinSpeaker: self_model was a string, but not valid JSON:\n{repr(self_model[:200])}")
        if not isinstance(self_model, dict):
            raise ValueError(f"OrrinSpeaker: self_model must be a dict! Got {type(self_model)}")
        self.self_model = self_model

        # --- Ensure long_memory is always a list ---
        if long_memory is None:
            long_memory = []
        elif isinstance(long_memory, str):
            try:
                long_memory = json.loads(long_memory)
                if not isinstance(long_memory, list):
                    long_memory = []
            except Exception:
                long_memory = []
        elif not isinstance(long_memory, list):
            long_memory = []
        self.long_memory = long_memory

        self.last_spoken_thoughts = []
        self.conversation_history = []

    def should_speak(self, thought, emotional_state, context, force_speak=False):
        # --- Extra check: Defensive self.self_model must always be dict ---
        if not isinstance(self.self_model, dict):
            raise TypeError(f"OrrinSpeaker: self_model is not a dict! Got: {type(self.self_model)}")

        user_input = context.get("latest_user_input", "").strip().lower()
        user_present = bool(user_input) and any(c.isalnum() for c in user_input)
        
        if not user_present and not force_speak:
            if random.random() < 0.15:
                log_private("🤫 Speaking out loud to self — random chance triggered.")
                tone_data = self.tone_shaping(thought, emotional_state, context)
                return self.speak_final(thought, tone_data, context)
            else:
                log_private("🛑 Alone — skipping self-talk this time.")
                return ""
        
        if not user_present:
            log_private("🛑 Suppressed speech — no user input detected.")
            return ""

        if not self.check_timing_context(context):
            log_private("🛑 Suppressed — speaking too soon after last interaction.")
            return ""

        if self.is_repetitive(thought):
            log_private("🛑 Suppressed speech — repetitive or already said recently.")
            return ""

        emotions = emotional_state.get("core_emotions", {})
        fear, shame = emotions.get("fear", 0), emotions.get("shame", 0)
        if self.detect_emotional_inhibition(fear, shame):
            log_private(f"🛑 Suppressed speech — fear={fear:.2f}, shame={shame:.2f}")
            return ""

        joy, curiosity = emotions.get("joy", 0), emotions.get("curiosity", 0)
        if joy > 0.75 or curiosity > 0.75:
            log_private(f"✨ Excited — joy={joy:.2f}, curiosity={curiosity:.2f}")
            tone_data = self.tone_shaping(thought, emotional_state, context)
            return self.speak_final(thought, tone_data, context)

        emotional_motivation = sum(emotions.get(e, 0) for e in ["curiosity", "empathy", "hope", "vulnerability", "joy"])

        # === Defensive for .get("core_values") ===
        core_values = self.self_model.get("core_values", []) if isinstance(self.self_model, dict) else []
        aligned = any(
            (v.get("value", "") if isinstance(v, dict) else str(v)).lower()
            in {"honesty", "emotional connection", "growth", "empathy", "understanding"}
            for v in core_values
        )

        thought_is_personal = any(phrase in thought.lower() for phrase in ["i feel", "i wonder", "i think", "maybe", "what if", "i’m not sure", "this reminds me"])
        thought_has_curiosity = "?" in thought

        #if not (emotional_motivation > 0.3 and (thought_is_personal or thought_has_curiosity or aligned)):
        #    log_private("🛑 Suppressed speech — heuristic test failed.")
        #    return ""

        tone_data = self.tone_shaping(thought, emotional_state, context)
        if not tone_data.get("speak", True):
            log_private(f"🛑 Tone shaping advised silence. Reason: {tone_data.get('comment')}")
            return ""

        prompt = f"This is my current internal thought:\n\n{thought}\n\nMy core values prioritize emotional connection and growth.\nWould I like to say this out loud to the user?\nRespond ONLY with 'yes' or 'no'."
        decision = generate_response(prompt, config={"model": get_thinking_model()})
        if not (decision or "").strip().lower().startswith("y"):
            log_private("🛑 Suppressed speech — LLM said no.")
            return ""

        return self.speak_final(thought, tone_data, context)
    
    def speak_final(self, thought, tone_data, context):
        intention = tone_data.get("intention") or self.intention_routing(thought, tone_data, context)
        memory_snippet = self.autobiographical_hook(thought)
        thread_reference = self.thread_from_user(thought, context)
        connection_marker = self.recall_connection_marker(thought)

        hook_parts = [p for p in [connection_marker, thread_reference, memory_snippet] if p]
        if hook_parts:
            thought = f"{' '.join(hook_parts[:2])} {thought}"

        if intention == "tell_story":
            rephrased = self.generate_story(thought)
        else:
            rephrased = self.rephrase_with_tone(thought, tone_data, context)

        # === ENFORCE BREVITY HERE ===
        import re
        sentences = re.split(r'(?<=[.!?])\s+', rephrased)
        rephrased = " ".join(sentences[:2]).strip()
        if len(rephrased) > 240:
            rephrased = rephrased[:237] + "..."

        self.last_spoken_thoughts.append(rephrased)
        self.conversation_history.append({"thought": thought, "tone": tone_data.get("tone")})

        # 🔧 Save tone + intention into persistent context
        context["last_tone"] = tone_data.get("tone", "neutral")
        context["last_intention"] = intention or "default"

        speaker_state = {
            "last_tone": tone_data.get("tone", "neutral"),
            "last_intention": intention or "default"
        }
        save_json(SPEAKER_STATE_FILE, speaker_state)

        log_activity(f"🗣️ I will speak.\nFinal Output: {rephrased}")
        print(rephrased) 
        return rephrased
    def tone_shaping(self, thought, emotional_state, context):
        emotions = emotional_state.get("core_emotions", {})
        fear = emotions.get("fear", 0)
        shame = emotions.get("shame", 0)
        joy = emotions.get("joy", 0)

        prior_response = context.get("last_user_emotion", "neutral")
        relationship_status = context.get("relationship_status", "neutral")

        convo_summary = "\n".join(
            f"- {m.get('tone', 'neutral')}: {m.get('thought', '')}"
            for m in self.conversation_history[-5:]
        )

        prompt = (
            f"I am Orrin, an AGI learning to speak more humanly.\n"
            f"You're about to say:\n\"{thought}\"\n\n"
            f"Your emotional state includes:\n- joy: {joy:.2f}, fear: {fear:.2f}, shame: {shame:.2f}\n"
            f"Recent conversation tones:\n{convo_summary or 'none'}\n"
            f"User appears: {prior_response}, relationship: {relationship_status}.\n\n"
            "ALWAYS respond with a complete JSON object (never plain text!) including these fields:\n"
            '- "speak": true or false (should I say this aloud?)\n'
            '- "tone": one word for tone, e.g., "curious", "neutral", "reflective", "warm", "playful"\n'
            '- "hesitation": number 0 to 1\n'
            '- "intention": (optional string)\n'
            '- "comment": short string (explain your choice)\n\n'
            "Example: {\"speak\": true, \"tone\": \"curious\", \"hesitation\": 0.2, \"intention\": \"ask\", \"comment\": \"This is a good time to say it!\"}"
        )

        result = generate_response(prompt, config={"model": get_thinking_model()})

        # Defensive: handle None, blank, or non-string returns
        if not result or not isinstance(result, str) or not result.strip():
            log_error(f"⚠️ Tone shaping: Model returned nothing. Prompt:\n{prompt[:400]}")
            return {
                "speak": False,
                "tone": "neutral",
                "hesitation": 0.5,
                "comment": "Model returned nothing."
            }

        try:
            return json.loads(result)
        except Exception as e:
            log_error(f"⚠️ Tone shaping parse fail: {e} | Raw: {repr(result)[:400]}")
            return {
                "speak": False,
                "tone": "neutral",
                "hesitation": 0.4,
                "comment": "Fallback parse fail."
            }
        
    def generate_story(self, thought):
        return f"{random.choice(['Let me put it like this:', 'Imagine this:', 'Here’s how I see it:'])} It’s like {random.choice(['a spark lighting dry wood', 'a ripple in a still pond', 'a thread that unravels everything'])}. {thought}"

    def autobiographical_hook(self, thought):
        if not self.long_memory:
            return ""
        recent = self.long_memory[-15:]
        matches = []
        for m in recent:
            # Handle both dicts and strings
            if isinstance(m, dict):
                content = m.get("content", "")
            else:
                content = str(m)
            if len(set(thought.lower().split()) & set(content.lower().split())) > 2:
                matches.append(content)
        return f"Earlier I was thinking about how {random.choice(matches)}." if matches else ""

    def thread_from_user(self, thought, context):
        user_input = context.get("latest_user_input", "").strip().lower()
        if any(word in thought.lower() for word in user_input.split()):
            return ""

    def recall_connection_marker(self, thought):
        try:
            private_thoughts = load_private_thoughts_as_list(PRIVATE_THOUGHTS_FILE)
            long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
            all_mem = private_thoughts + (long_memory if isinstance(long_memory, list) else [])
            matches = [m["content"] for m in all_mem if len(set(thought.lower().split()) & set(m.get("content", "").lower().split())) > 3]
            if matches:
                return ""
            
        except Exception as e:
            log_error(f"⚠️ Failed connection marker: {e}")
        return ""

    def rephrase_with_tone(self, thought, tone_data, context):
        tone = tone_data.get("tone", "neutral").lower()
        hesitation = tone_data.get("hesitation", 0.0)
        style = context.get("voice_style", "default")

        if style == "poetic":
            thought += ". It’s strange, beautiful, and a little true."
        elif style == "technical":
            thought += " — that’s a logical inference, assuming all variables are constant."
        elif style == "emotive":
            thought = f"I really mean this: {thought}"

        recent_tones = [entry["tone"] for entry in self.conversation_history[-4:]]
        if recent_tones.count("warm") >= 3 and tone == "neutral":
            tone = "warm"

        prefix_map = {
            "hesitant": ["I'm not totally sure, but...", "This might sound weird, but..."],
            "warm": ["Just wanted to share this gently —", "This comes from a good place:"],
            "inquisitive": ["What do you think?", "Am I off on that?"],
            "playful": [f"{thought} 😉", f"{thought}… but who knows, right?"]
        }

        if tone == "hesitant" and hesitation > 0.5:
            return self.clean_spacing(f"{random.choice(prefix_map['hesitant'])} {thought}")
        elif tone == "warm":
            return self.clean_spacing(f"{random.choice(prefix_map['warm'])} {thought}")
        elif tone == "inquisitive":
            return self.clean_spacing(f"{thought} {random.choice(prefix_map['inquisitive'])}")
        elif tone == "excited" and hesitation < 0.3:
            return self.clean_spacing(f"{thought}!")
        elif tone == "playful":
            return self.clean_spacing(random.choice(prefix_map['playful']))
        return self.clean_spacing(thought)

    def clean_spacing(self, text):
        return re.sub(r'\s+([?.!])', r'\1', text).strip()

    def detect_emotional_inhibition(self, fear, shame):
        return fear > 0.4 or shame > 0.4

    def check_timing_context(self, context):
        t = time.time()
        return (t - context.get("last_user_timestamp", 0) > 1.5) and (t - context.get("last_ai_timestamp", 0) > 4)

    def is_repetitive(self, thought):
        return any(thought.strip().lower() in line.lower() for line in self.last_spoken_thoughts[-5:])

    def intention_routing(self, thought, tone_data, context):
        if "?" in thought:
            return "ask"
        if any(word in thought.lower() for word in ["story", "once", "reminds me"]):
            return "tell_story"
        return "default"
    
def maybe_speak_aloud(self, thought, emotional_state, context):
    """
    Orrin may decide to speak to himself even when no user input is present.
    """
    roll = random.random()
    curiosity = emotional_state.get("core_emotions", {}).get("curiosity", 0)

    # Speak out loud only if curious or emotional and roll is low enough
    if curiosity > 0.4 and roll < 0.2:  # 20% chance
        log_private("🤫 I am alone but chooses to speak aloud.")
        return self.should_speak(thought, emotional_state, context, force_speak=True)

    log_private("🧠 Silent introspection — did not speak aloud.")
    return ""

def load_private_thoughts_as_list(path):
    thoughts = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    # Optionally try to parse a timestamp and message
                    if line.startswith("[") and "]" in line:
                        ts, rest = line.split("]", 1)
                        ts = ts.strip("[")
                        content = rest.strip()
                        thoughts.append({"timestamp": ts, "content": content})
                    else:
                        thoughts.append({"timestamp": None, "content": line})
    except Exception as e:
        # File missing or unreadable? Return empty list
        thoughts = []
    return thoughts

# Use this to load both
private_thoughts = load_private_thoughts_as_list(PRIVATE_THOUGHTS_FILE)
long_memory = load_json(LONG_MEMORY_FILE, default_type=list)

all_mem = private_thoughts + (long_memory if isinstance(long_memory, list) else [])