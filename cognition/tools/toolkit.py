#imports
import os
import json
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from utils.json_utils import (
    load_json,
    save_json,
    extract_json
)
from utils.log import (
    log_activity, 
    log_error, 
    log_model_issue, 
    log_private
)
from paths import TOOL_REQUESTS_FILE, LONG_MEMORY_FILE, WORKING_MEMORY_FILE
from utils.core_utils import get_thinking_model
from utils.generate_response import generate_response

#functions
def delay_between_requests():
    time.sleep(random.uniform(2, 5))

def add_tool_to_catalog(name, description, when_to_use):
    catalog_path = "tool_catalog.json"
    try:
        tool_catalog = load_json(catalog_path, default_type=list)
    except Exception:
        tool_catalog = []

    new_tool = {
        "name": name,
        "description": description,
        "when_to_use": when_to_use,
        "discovered": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    for tool in tool_catalog:
        if tool.get("name") == name:
            log_private(f"⚠️ Tool '{name}' already exists in the catalog.")
            return

    tool_catalog.append(new_tool)
    save_json(catalog_path, tool_catalog)
    log_private(f"✅ Tool '{name}' added to catalog.")

def is_scraping_allowed(url):
    from urllib.robotparser import RobotFileParser
    from urllib.parse import urlparse

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except:
        return False

def web_search(query):
    import requests
    url = "https://api.serper.dev/search"
    headers = {"X-API-KEY": os.getenv("SERPER_API_KEY")}
    params = {"q": query}
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json()
    except Exception as e:
        log_error(f"[web_search] Failed: {e}")
        return {}

def evaluate_tool_use(memories):
    keywords = {
        "search": ["look up", "google", "find info", "get data", "browse"],
        "run_python": ["calculate", "plot", "simulate", "compute", "graph"]
    }

    existing = load_json(TOOL_REQUESTS_FILE, default_type=list)
    if not isinstance(existing, list):
        existing = []

    existing_keys = {(e.get("tool"), e.get("reason")) for e in existing if isinstance(e, dict)}

    for m in memories:
        if not isinstance(m, dict):
            continue
        text = m.get("content", "").lower()
        for tool, cues in keywords.items():
            if any(cue in text for cue in cues):
                entry = {
                    "tool": tool,
                    "reason": m.get("content", ""),
                    "timestamp": m.get("timestamp", datetime.now(timezone.utc).isoformat())
                }
                key = (entry["tool"], entry["reason"])
                if key not in existing_keys:
                    existing.append(entry)
                    existing_keys.add(key)

    save_json(TOOL_REQUESTS_FILE, existing)

def tool_thinking():
    recent_memories = (
        load_json(LONG_MEMORY_FILE, default_type=list)[-15:] +
        load_json(WORKING_MEMORY_FILE, default_type=list)[-5:]
    )

    prompt = (
        "I am a reflective AI.\n"
        "From the following thoughts, identify any that might benefit from tool use like web search, Python code, or visualization.\n"
        "If so, describe:\n"
        "- which tool I would use\n"
        "- what question or goal I would pursue with it\n"
        "- why it's useful\n\n"
        "Only respond with a JSON array of entries like:\n"
        "[{\"tool\": \"search\", \"reason\": \"Find background info on X\", \"timestamp\": \"...\"}, ...]\n\n"
        "Here are the recent thoughts:\n"
        + "\n".join(f"- {m['content']}" for m in recent_memories if isinstance(m, dict) and "content" in m)
    )

    config = {"model": get_thinking_model()}
    response = generate_response(prompt, config=config)

    if not response:
        log_model_issue("tool_thinking() produced no response.")
        return

    try:
        suggestions = extract_json(response)
        if isinstance(suggestions, list):
            existing = load_json(TOOL_REQUESTS_FILE, default_type=list)
            if not isinstance(existing, list):
                log_error("tool_requests.json was not a list. Resetting.")
                existing = []
            merged = existing + [s for s in suggestions if isinstance(s, dict)]
            save_json(TOOL_REQUESTS_FILE, merged)

            log_activity(f"Orrin added {len(suggestions)} tool request(s).")
            log_private(f"Orrin reflected on tool use and added:\n{json.dumps(suggestions, indent=2)}")
        else:
            log_model_issue(f"tool_thinking() returned non-list structure:\n{response}")
    except Exception as e:
        log_error(f"Failed to parse tool suggestions in tool_thinking(): {e}\nRaw: {response}")
def scrape_text(url):
    import requests
    if not is_scraping_allowed(url):
        return "⚠️ Scraping disallowed by robots.txt."

    delay_between_requests()

    try:
        response = requests.get(url, timeout=10, headers={
            "User-Agent": "OrrinBot/1.0 (ethical AGI; contact: ric.massey@gmail.com)"
        })
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text()[:2000]
    except Exception as e:
        return f"❌ Scrape failed: {str(e)}"