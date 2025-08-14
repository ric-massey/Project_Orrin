import time
import json
import random
import re
from datetime import datetime, timezone

from memory.chat_log import log_raw_user_input, wrap_text
from utils.log import log_private, log_activity, log_error
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import load_json, save_json
from paths import PRIVATE_THOUGHTS_FILE, LONG_MEMORY_FILE, SPEAKER_STATE_FILE

def filter_memories(memories, tag="[MemoryFilter]"):
    """Filter input list to only dicts, logging any weird entries."""
    if not isinstance(memories, list):
        log_error(f"{tag} Expected list, got {type(memories)}: {memories}")
        return []
    filtered = []
    for i, m in enumerate(memories):
        if isinstance(m, dict):
            filtered.append(m)
        else:
            log_private(f"{tag} Non-dict at index {i}: {repr(m)[:120]} (type: {type(m)})")
    return filtered

class OrrinSpeaker:
    def __init__(self, self_model, long_memory=None):
        # Defensive: self_model must be dict
        if isinstance(self_model, str):
            try:
                self_model = json.loads(self_model)
            except Exception:
                raise ValueError(
                    f"OrrinSpeaker: self_model was a string, but not valid JSON:\n{repr(self_model[:200])}"
                )
        if not isinstance(self_model, dict):
            raise ValueError(f"OrrinSpeaker: self_model must be a dict! Got {type(self_model)}")
        self.self_model = self_model

        # Defensive: long_memory must be list of dicts
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
        self.long_memory = filter_memories(long_memory, tag="[Init:long_memory]")

        self.last_spoken_thoughts = []
        self.conversation_history = []

    def maybe_speak_aloud(self, thought, emotional_state, context):
        roll = random.random()
        curiosity = emotional_state.get("core_emotions", {}).get("curiosity", 0)
        if curiosity > 0.4 and roll < 0.2:
            log_private("🤫 I am alone but choose to speak aloud.")
            return self.should_speak(thought, emotional_state, context, force_speak=True)
        log_private("🧠 Silent introspection — did not speak aloud.")
        return ""

    def should_speak(self, thought, emotional_state, context, force_speak=False):
        if not isinstance(self.self_model, dict):
            raise TypeError(f"OrrinSpeaker: self_model is not a dict! Got: {type(self.self_model)}")

        user_input = context.get("latest_user_input", "").strip().lower()
        user_present = bool(user_input) and any(c.isalnum() for c in user_input)

        if not user_present and not force_speak:
            if random.random() < 0.15:
                log_private("🤫 Speaking out loud to self")
                tone_data = self.tone_shaping(thought, emotional_state, context)
                return self.speak_final(thought, tone_data, context)
            else:
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

        tone_data = self.tone_shaping(thought, emotional_state, context)
        if not tone_data.get("speak", True):
            log_private(f"🛑 Tone shaping advised silence. Reason: {tone_data.get('comment')}")
            return ""

        prompt = (
            f"This is my current internal thought:\n\n{thought}\n\n"
            "My core values prioritize emotional connection and growth.\n"
            "Would I like to say this out loud to the user?\n"
            "Respond ONLY with 'yes' or 'no'."
        )
        decision = (generate_response(prompt, config={"model": get_thinking_model()}) or "").strip().lower()
        if not decision.startswith("y"):
            log_private("🛑 Suppressed speech — LLM said no.")
            return ""

        return self.speak_final(thought, tone_data, context)

    def speak_final(self, thought, tone_data, context):
        intention = tone_data.get("intention") or self.intention_routing(thought, tone_data, context)
        memory_snippet = self.autobiographical_hook(thought)
        thread_reference = self.thread_from_user(thought, context)
        connection_marker = self.recall_connection_marker(thought)

        hook_parts = [p for p in (connection_marker, thread_reference, memory_snippet) if p]
        if hook_parts:
            thought = f"{' '.join(hook_parts[:2])} {thought}"

        if intention == "tell_story":
            rephrased = self.generate_story(thought)
        else:
            rephrased = self.rephrase_with_tone(thought, tone_data, context)

        if len(rephrased) > 400:
            rephrased = rephrased[:397] + "…"

        rephrased_wrapped = wrap_text(rephrased, width=85)
        self.last_spoken_thoughts.append(rephrased)
        self.conversation_history.append({"thought": thought, "tone": tone_data.get("tone")})
        context["last_tone"] = tone_data.get("tone", "neutral")
        context["last_intention"] = intention or "default"

        speaker_state = {
            "last_tone": tone_data.get("tone", "neutral"),
            "last_intention": intention or "default",
        }
        save_json(SPEAKER_STATE_FILE, speaker_state)

        log_activity(f"🗣️ I will speak.\nFinal Output:\n{rephrased_wrapped}")

        user_input = context.get("latest_user_input", "—") or "(no user input)"
        log_raw_user_input({
            "user": user_input.strip() or "(no user input)",
            "orrin": rephrased_wrapped,
            "influence": context.get("relationship", {}).get("influence_score", 0.5),
            "emotional_effect": context.get("relationship", {}).get("recent_emotional_effect", "neutral"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return rephrased_wrapped

    def tone_shaping(self, thought, emotional_state, context):
        emotions = emotional_state.get("core_emotions", {})
        fear = emotions.get("fear", 0.0)
        shame = emotions.get("shame", 0.0)
        joy = emotions.get("joy", 0.0)
        prior_response = context.get("last_user_emotion", "neutral")
        relationship_status = context.get("relationship_status", "neutral")

        convo_summary = "\n".join(
            f"- {m.get('tone', 'neutral')}: {m.get('thought', '')}"
            for m in self.conversation_history[-5:]
            if isinstance(m, dict)
        )

        prompt = (
            "I am Orrin, an AGI learning to speak more humanly.\n"
            f"You're about to say:\n\"{thought}\"\n\n"
            f"Your emotional state includes:\n- joy: {joy:.2f}, fear: {fear:.2f}, shame: {shame:.2f}\n"
            f"Recent conversation tones:\n{convo_summary or 'none'}\n"
            f"User appears: {prior_response}, relationship: {relationship_status}.\n\n"
            "ALWAYS respond with a complete JSON object (never plain text!) including:\n"
            '- "speak": true/false\n'
            '- "tone": one word, e.g., "curious", "neutral", "reflective", "warm", "playful"\n'
            '- "hesitation": 0..1\n'
            '- "intention": (optional string)\n'
            '- "comment": short string\n'
            'Example: {"speak": true, "tone": "curious", "hesitation": 0.2, "intention": "ask", "comment": "Good timing"}'
        )
        result = generate_response(prompt, config={"model": get_thinking_model()})
        if not (isinstance(result, str) and result.strip()):
            log_error(f"⚠️ Tone shaping: Model returned nothing.")
            return {"speak": False, "tone": "neutral", "hesitation": 0.5, "comment": "Model returned nothing."}
        try:
            return json.loads(result)
        except Exception as e:
            log_error(f"⚠️ Tone shaping parse fail: {e} | Raw: {repr(result)[:400]}")
            return {"speak": False, "tone": "neutral", "hesitation": 0.4, "comment": "Fallback parse fail."}

    def generate_story(self, thought):
        return (
            f"{random.choice(['Let me put it like this:', 'Imagine this:', 'Here’s how I see it:'])} "
            f"It’s like {random.choice(['a spark lighting dry wood', 'a ripple in a still pond', 'a thread that unravels everything'])}. "
            f"{thought}"
        )

    def autobiographical_hook(self, thought):
        recent = filter_memories(self.long_memory[-15:], tag="[autobiographical_hook]")
        matches = []
        twords = set(thought.lower().split())
        for m in recent:
            content = m.get("content", "")
            if len(twords & set(content.lower().split())) > 2:
                matches.append(content)
        return f"Earlier I was thinking about how {random.choice(matches)}." if matches else ""

    def thread_from_user(self, thought, context):
        user_input = context.get("latest_user_input", "").strip().lower()
        if not user_input:
            return ""
        if any(word and word in thought.lower() for word in user_input.split()):
            return ""
        return ""  # explicit default

    def recall_connection_marker(self, thought):
        try:
            private_thoughts = filter_memories(
                load_private_thoughts_as_list(PRIVATE_THOUGHTS_FILE),
                tag="[recall_connection_marker:private_thoughts]"
            )
            long_memory = filter_memories(
                load_json(LONG_MEMORY_FILE, default_type=list),
                tag="[recall_connection_marker:long_memory]"
            )
            all_mem = private_thoughts + long_memory
            twords = set(thought.lower().split())
            matches = [m["content"] for m in all_mem if len(twords & set(m.get("content", "").lower().split())) > 3]
            if matches:
                # If you want a visible marker, return a short phrase; empty string keeps output minimal
                return ""
        except Exception as e:
            log_error(f"⚠️ Failed connection marker: {e}")
        return ""

    def rephrase_with_tone(self, thought, tone_data, context):
        tone = str(tone_data.get("tone", "neutral")).lower()
        hesitation = float(tone_data.get("hesitation", 0.0) or 0.0)
        style = context.get("voice_style", "default")

        if style == "poetic":
            thought += ". It’s strange, beautiful, and a little true."
        elif style == "technical":
            thought += " — that’s a logical inference, assuming all variables are constant."
        elif style == "emotive":
            thought = f"I really mean this: {thought}"

        recent_tones = [
            entry.get("tone", "neutral")
            for entry in self.conversation_history[-4:]
            if isinstance(entry, dict)
        ]
        if recent_tones.count("warm") >= 3 and tone == "neutral":
            tone = "warm"

        prefix_map = {
            "hesitant": ["I'm not totally sure, but", "This might sound weird, but"],
            "warm": ["Just wanted to share this gently —", "This comes from a good place:"],
            "inquisitive": ["What do you think?", "Am I off on that?"],
            "playful": [f"{thought} 😉", f"{thought} but who knows, right?"],
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
        return re.sub(r"\s+([?.!])", r"\1", text).strip()

    def detect_emotional_inhibition(self, fear, shame):
        return float(fear) > 0.4 or float(shame) > 0.4

    def check_timing_context(self, context):
        t = time.time()
        return (t - float(context.get("last_user_timestamp", 0)) > 1.5) and \
               (t - float(context.get("last_ai_timestamp", 0)) > 4.0)

    def is_repetitive(self, thought):
        t = thought.strip().lower()
        return any(t in line.lower() for line in self.last_spoken_thoughts[-5:])

    def intention_routing(self, thought, tone_data, context):
        if "?" in thought:
            return "ask"
        if any(word in thought.lower() for word in ["story", "once", "reminds me"]):
            return "tell_story"
        return "default"

def load_private_thoughts_as_list(path):
    """Parse PRIVATE_THOUGHTS_FILE into a list of dicts with {timestamp, content}."""
    thoughts = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and "]" in line:
                    ts, rest = line.split("]", 1)
                    ts = ts.strip("[")
                    content = rest.strip()
                    thoughts.append({"timestamp": ts, "content": content})
                else:
                    thoughts.append({"timestamp": None, "content": line})
    except Exception as e:
        log_error(f"[load_private_thoughts_as_list] Failed: {e}")
        thoughts = []

    filtered = []
    for i, t in enumerate(thoughts):
        if isinstance(t, dict):
            filtered.append(t)
        else:
            log_private(f"[PrivateThoughtsFilter] Non-dict at {i}: {repr(t)} ({type(t)})")
    return filtered

# Helpers you can call elsewhere (avoid I/O at import time)
def get_all_memories():
    private_thoughts = load_private_thoughts_as_list(PRIVATE_THOUGHTS_FILE)
    long_memory = filter_memories(load_json(LONG_MEMORY_FILE, default_type=list), tag="[LongMemoryLoad]")
    return private_thoughts + long_memory