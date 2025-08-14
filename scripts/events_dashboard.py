# Tiny CLI to summarize events.jsonl
import json, sys, os
from collections import Counter
from paths import EVENTS_LOG

def load_events():
    if not os.path.exists(EVENTS_LOG):
        print("No events log found:", EVENTS_LOG)
        return []
    evs = []
    with open(EVENTS_LOG, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                evs.append(json.loads(s))
            except Exception as e:
                # skip malformed line, but tell the user which one
                print(f"⚠️  Skipping malformed JSON at line {i}: {e}", file=sys.stderr)
    return evs

def main():
    evs = load_events()
    if not evs:
        return

    kinds = Counter(e.get("kind", "UNKNOWN") for e in evs)
    print("Events by kind:")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")

    # Success rate for completed actions
    actions = [e for e in evs if e.get("kind") == "ACTION_END"]
    ok = sum(1 for e in actions if e.get("status") == "ok")
    if actions:
        print(f"Action success rate: {ok}/{len(actions)} = {ok/len(actions):.1%}")
    else:
        print("No actions recorded.")

if __name__ == "__main__":
    main()