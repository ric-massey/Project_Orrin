#imports
import json, time
from datetime import datetime, timezone

from utils.json_utils import (
    load_json, 
    save_json
)
from paths import (
    TOOL_REQUESTS_FILE, LONG_MEMORY_FILE,
)
from behavior.tools.toolkit import scrape_text
from utils.generate_response import generate_response
from memory.working_memory import update_working_memory
from utils.emotion_utils import detect_emotion
from utils.log import log_model_issue, log_private

#functions
def run_python(code):
    try:
        result = eval(code, {}, {})
        return str(result)
    except Exception as e:
        return f"Python error: {e}"

def run_search(query):
    prompt = (
        f"I need to answer the query: '{query}'\n"
        "Suggest one good web page URL that is likely to contain the answer and can be scraped. "
        "Respond with only the full URL. Do not explain."
    )
    url = generate_response(prompt)
    if not isinstance(url, str) or not url.startswith("http"):
        return f"Invalid URL generated: {url}"
    scraped = scrape_text(url)
    return f"URL: {url}\n\nScraped content:\n{scraped}"

def run_tool(tool, reason):
    if tool == "run_python":
        return run_python(reason)
    elif tool == "search":
        return run_search(reason)
    else:
        return f"Unknown tool: {tool}"

def reflect_on_result(tool, reason, result):
    prompt = (
        f"I used the `{tool}` tool for:\n'{reason}'\n\n"
        f"The result was:\n{result[:1000]}\n\n"
        "Reflect:\n"
        "- What does this suggest?\n"
        "- Should I follow up?\n"
        "- Should anything be added to memory?\n\n"
        "Respond with plain reflection or a JSON tool request."
    )
    response = generate_response(prompt)

    try:
        new_requests = json.loads(response)
        if isinstance(new_requests, list):
            existing = load_json(TOOL_REQUESTS_FILE, default_type=list)
            for r in new_requests:
                if not isinstance(r, dict):
                    continue
                r.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                r.setdefault("executed", False)
            save_json(TOOL_REQUESTS_FILE, existing + new_requests)
            return f"🧠 Follow-up tool request(s) added: {new_requests}"
    except Exception as e:
        log_model_issue(f"[reflect_on_result] Failed to parse JSON tool request: {e}\nRaw: {response}")
    return f"🧠 Reflection: {response}"

def execute_pending_tools():
    requests_data = load_json(TOOL_REQUESTS_FILE, default_type=list)
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    updated = False

    for entry in requests_data:
        if not isinstance(entry, dict) or entry.get("executed"):
            continue

        tool = entry.get("tool")
        reason = entry.get("reason")
        if not tool or not reason:
            continue

        log_private(f"🔧 Executing `{tool}`: {reason}")
        result = run_tool(tool, reason)
        reflection = reflect_on_result(tool, reason, result)

        timestamp = datetime.now(timezone.utc).isoformat()
        long_memory.append({
            "content": f"Tool `{tool}` used for `{reason}` → {result[:300]}...",
            "emotion": detect_emotion(result),
            "timestamp": timestamp
        })
        long_memory.append({
            "content": reflection,
            "emotion": detect_emotion(reflection),
            "timestamp": timestamp
        })
        existing = load_json(LONG_MEMORY_FILE, default_type=list)
        existing.append(long_memory)
        save_json(LONG_MEMORY_FILE, existing)

        update_working_memory(f"Tool `{tool}` executed: {reason} → {result[:300]}")
        entry["executed"] = True
        entry["executed_at"] = timestamp
        updated = True

    if updated:
        save_json(TOOL_REQUESTS_FILE, requests_data)
        log_private("✅ Tool execution pass complete.")

if __name__ == "__main__":
    while True:
        execute_pending_tools()
        time.sleep(6)