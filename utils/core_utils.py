import os
import re
import time
import random
from utils.json_utils import (
    load_json, 
    save_json,
    extract_json
)
from config.settings import model_roles
from utils.log import log_model_issue
from dotenv import load_dotenv
from utils.generate_response import generate_response, get_thinking_model

load_dotenv()
from openai import OpenAI
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
        knowledge = extract_json(response)
        if isinstance(knowledge, list):
            existing = load_json("KNOWLEDGE", default_type=list)
            save_json("KNOWLEDGE", existing + knowledge)
    except Exception as e:
        log_model_issue(f"[extract_knowledge_from_reflection] Failed to parse or save: {e}")

def extract_questions(text):
    return [q.strip() for q in re.findall(r'([A-Z][^?!.]*\?)', text) if len(q.strip()) > 10]

def rate_satisfaction(thought):
    prompt = (
        f"Reflect on this thought:\n{thought}\n\n"
        "On a scale from 0 to 1, how satisfying or complete is this answer? "
        "Respond ONLY with a float between 0.0 and 1.0."
    )
    try:
        model_name = get_thinking_model()
        if isinstance(model_name, dict):
            model_name = model_name.get("model", "gpt-4.1")

        response = generate_response(prompt, model=model_name)
        if response:
            match = re.search(r"\d\.\d+", response)
            return float(match.group()) if match else 0.0
    except Exception as e:
        log_model_issue(f"[rate_satisfaction] Failed to parse float: {e}")
    return 0.0

def delay_between_requests(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def extract_lessons(memories):
    lessons = []
    for m in memories:
        try:
            content = m.get("content", "").strip()
            if content.lower().startswith("lesson:"):
                lesson_text = content[7:].strip()
                if lesson_text:
                    lessons.append(lesson_text)
        except Exception:
            continue
    return lessons