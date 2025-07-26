import os
import re
import time
from datetime import datetime, timezone
import random
import uuid
from dotenv import load_dotenv
from openai import OpenAI
from emotion.emotion import detect_emotion
from utils.json_utils import (
    load_json, 
    save_json,
    extract_json
)
from core.config.settings import model_roles
from utils.log import log_model_issue
from utils.generate_response import generate_response, get_thinking_model
from paths import KNOWLEDGE 

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_human_model():
    return model_roles.get("human_facing", "gpt-4.1")

def extract_knowledge_from_reflection(reflection_text):
    prompt = (
        "Extract reusable insights or principles from the following:\n\n"
        f"{reflection_text}\n\nRespond ONLY with a JSON list of short knowledge snippets."
    )
    response = generate_response(prompt)
    try:
        snippets = extract_json(response)
        if not isinstance(snippets, list):
            raise ValueError("Response is not a list")

        existing = load_json(KNOWLEDGE, default_type=list)
        existing_summaries = {e.get("summary") for e in existing if "summary" in e}

        for snippet in snippets:
            text = snippet if isinstance(snippet, str) else snippet.get("summary", "")
            if not text or text in existing_summaries:
                continue  # skip empty or duplicates

            # Basic keyword extraction fallback
            keywords = set()
            for word in text.lower().split():
                if len(word) > 3 and word.isalpha():
                    keywords.add(word)

            # Alternatively, use extract_keywords() if you implement it
            # keywords = extract_keywords(text)

            entry = {
                "id": str(uuid.uuid4()),
                "summary": text,
                "source": reflection_text[:80],  # Optionally hash for uniqueness
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "reflection",
                "emotion": detect_emotion(text),  # Emotion on snippet itself
                "confidence": 0.8,  # Placeholder, adjust dynamically later
                "relevance": list(keywords),
                "reference_count": 0,
            }
            existing.append(entry)

        save_json(KNOWLEDGE, existing)

    except Exception as e:
        log_model_issue(f"[extract_knowledge_from_reflection] Failed to parse or save: {e}")

def extract_questions(text):
    # Extract questions starting with capital letter and ending with ?
    return [q.strip() for q in re.findall(r'([A-Z][^?!.]*\?)', text) if len(q.strip()) > 10]

import re

def rate_satisfaction(thought):
    prompt = (
        f"Reflect on this thought:\n{thought}\n\n"
        "On a scale from 0 to 1, how satisfying or complete is this answer?\n"
        "Respond ONLY with a single float (like 0.0, 0.7, or 1.0) and NO other words or explanation."
    )
    try:
        model_name = get_thinking_model()
        if isinstance(model_name, dict):
            model_name = model_name.get("model", "gpt-4.1")
        response = generate_response(prompt, model=model_name)
        print(f"[rate_satisfaction] Raw LLM response: {repr(response)}")  # Debug

        # Accept numbers like 1, 1.0, 0, 0.5, .8, etc.
        match = re.search(r"\d*\.?\d+", response)
        if match:
            val = float(match.group())
            if 0.0 <= val <= 1.0:
                return val
        # Final fallback: check if "1" or "0" is alone in the response
        if response.strip() == "1":
            return 1.0
        if response.strip() == "0":
            return 0.0
    except Exception as e:
        log_model_issue(f"[rate_satisfaction] Failed to parse float: {e}")
    return 0.0

def delay_between_requests(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def extract_lessons(memories):
    lessons = []
    for m in memories:
        try:
            # 1. Check explicit lesson key first (future-proof)
            if "lesson" in m:
                lesson_text = str(m["lesson"]).strip()
                if lesson_text:
                    lessons.append(lesson_text)
                continue

            # 2. Fallback to 'content' text matching
            content = m.get("content", "").strip()
            # Lowercase and check for a few common patterns
            lower = content.lower()
            if lower.startswith("lesson:"):
                lesson_text = content[7:].strip()
                if lesson_text:
                    lessons.append(lesson_text)
            elif lower.startswith("lesson learned:"):
                lesson_text = content[15:].strip()
                if lesson_text:
                    lessons.append(lesson_text)
            # Optionally: Only pull from memories marked as event_type='lesson'
            # if m.get("event_type") == "lesson":
            #     lessons.append(content)
        except Exception:
            continue
    return lessons