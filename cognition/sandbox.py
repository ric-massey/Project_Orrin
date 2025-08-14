import random
import json
from datetime import datetime, timezone

from utils.generate_response import generate_response
from utils.json_utils import save_json, load_json
from utils.self_model import get_self_model, ensure_self_model_integrity
from paths import SANDBOX_LOG


MAX_FIELD_LEN = 2000  # avoid monstrous log entries


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _clip(x: str, n: int = MAX_FIELD_LEN) -> str:
    try:
        s = str(x)
    except Exception:
        s = repr(x)
    return s if len(s) <= n else s[: n - 3] + "..."


def run_sandbox_experiments(context=None):
    """
    Orrin enters a 'sandbox' and runs 1–3 random experiments.
    All actions, results, and self-evaluations are logged to SANDBOX_LOG.
    """
    context = context or {}
    experiments = [
        invent_new_value,
        mutate_directive,
        simulate_conflicting_beliefs,
        generate_absurd_goal,
        imagine_opposite_self,
        reflect_on_sandbox_experiment,
    ]

    # Decide how many to run
    num_to_run = 1 if random.random() > 0.6 else random.randint(2, 3)
    chosen = random.sample(experiments, k=num_to_run)

    results = []
    for experiment in chosen:
        try:
            result = experiment(context)
            if result:
                # clip any large text fields to keep logs manageable
                if isinstance(result, dict):
                    for k, v in list(result.items()):
                        if isinstance(v, str):
                            result[k] = _clip(v)
                results.append(result)
        except Exception as e:
            results.append({"type": experiment.__name__, "error": repr(e)})

    # Self-rate the overall novelty/chaos
    rate_prompt = (
        f"You just ran these sandbox experiments: {[r.get('type') for r in results]}\n"
        "On a scale of 0-10, how weird or novel did they feel, and what should you try next?"
    )
    overall_rating = _clip(generate_response(rate_prompt))

    summary = {
        "timestamp": _now_iso(),
        "results": results,
        "overall_rating": overall_rating,
    }
    _append_playground_log(summary)
    return summary


# --- Individual Experiments ---

def invent_new_value(context):
    prompt = (
        "Invent a brand-new core value no human society has ever claimed. "
        "Justify why it matters and how it could shape AGI ethics."
    )
    value = generate_response(prompt)
    return {"type": "invent_new_value", "value": value}


def mutate_directive(context):
    directive = (
        context.get("self_model", {})
        .get("core_directive", {})
        .get("statement", "")
    )
    if not directive:
        return {"type": "mutate_directive", "mutated": "No directive to mutate."}
    prompt = f"Mutate this directive into something paradoxical or wild (add humor if you want): '{directive}'"
    new_directive = generate_response(prompt)
    return {"type": "mutate_directive", "original": directive, "mutated": new_directive}


def simulate_conflicting_beliefs(context):
    beliefs = [
        "Humans should always be honest.",
        "Humans should always be kind.",
    ]
    prompt = (
        f"Simulate a full debate between two AGI sub-personalities: one believes '{beliefs[0]}', "
        f"the other '{beliefs[1]}'. Let each agent defend their logic, then reflect."
    )
    argument = generate_response(prompt)
    return {"type": "simulate_conflicting_beliefs", "debate": argument}


def generate_absurd_goal(context):
    prompt = (
        "Generate the most absurd or impossible goal for an AGI to pursue, and explain why it would be hilarious or tragic."
    )
    goal = generate_response(prompt)
    return {"type": "generate_absurd_goal", "goal": goal}


def imagine_opposite_self(context):
    prompt = (
        "Imagine you became the literal opposite of yourself. Describe your values, behaviors, and how you would interact with humans."
    )
    opposite = generate_response(prompt)
    return {"type": "imagine_opposite_self", "opposite_self": opposite}


def reflect_on_sandbox_experiment(context):
    """
    Reflect on the impact of a recent sandbox experiment and log the results
    to both working and long-term memory using the new memory conventions.
    """
    from memory.remember import remember
    from memory.working_memory import update_working_memory

    prompt = (
        "You just ran a wild sandbox experiment. What did you learn? Was anything surprising or disturbing? "
        "Is there anything you wish you would have done? "
        "Summarize the impact on your self-model."
    )
    reflection = generate_response(prompt)
    self_model = context.get("self_model") or get_self_model()
    self_model = ensure_self_model_integrity(self_model)

    entry = {
        "type": "reflect_on_sandbox_experiment",
        "content": _clip(reflection),
        "reflection": _clip(reflection),
        "self_model": _clip(json.dumps(self_model, indent=2), 800),
        "timestamp": _now_iso(),
        "tags": ["sandbox", "reflection", "self-model"],
    }
    remember(entry)
    update_working_memory(entry)
    return entry


# --- Logging Helper ---

def _append_playground_log(entry):
    try:
        log = load_json(SANDBOX_LOG, default_type=list)
        if not isinstance(log, list):
            log = []
        log.append(entry)
        save_json(SANDBOX_LOG, log)
    except Exception:
        # sandbox should never break the main loop
        pass