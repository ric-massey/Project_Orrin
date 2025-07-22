import random
import json
from datetime import datetime, timezone
from utils.generate_response import generate_response
from utils.json_utils import save_json, load_json
from utils.self_model import get_self_model
from paths import SANDBOX_LOG


def run_sandbox_experiments(context):
    """
    Orrin enters a 'sandbox' and runs a random experiment.
    All actions, results, and self-evaluations are logged.
    """
    experiments = [
        invent_new_value,
        mutate_directive,
        simulate_conflicting_beliefs,
        generate_absurd_goal,
        imagine_opposite_self,
        reflect_on_sandbox_experiment,
    ]
    # Chance to run multiple experiments for extra chaos
    num_to_run = 1 if random.random() > 0.6 else random.randint(2, 3)
    chosen = random.sample(experiments, k=num_to_run)

    results = []
    for experiment in chosen:
        result = experiment(context)
        if result:
            results.append(result)

    # Optionally: Ask Orrin to self-rate the overall chaos/novelty
    rate_prompt = (
        f"You just ran these sandbox experiments: {[r['type'] for r in results]}\n"
        "On a scale of 0-10, how weird or novel did they feel, and what should you try next?"
    )
    overall_rating = generate_response(rate_prompt)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "overall_rating": overall_rating,
    }
    _append_playground_log(summary)
    return summary

# --- Individual Experiments ---

def invent_new_value(context):
    prompt = "Invent a brand-new core value no human society has ever claimed. Justify why it matters and how it could shape AGI ethics."
    value = generate_response(prompt)
    return {"type": "invent_new_value", "value": value}

def mutate_directive(context):
    directive = context.get("self_model", {}).get("core_directive", {}).get("statement", "")
    if not directive:
        return {"type": "mutate_directive", "mutated": "No directive to mutate."}
    prompt = f"Mutate this directive into something paradoxical or wild (add humor if you want): '{directive}'"
    new_directive = generate_response(prompt)
    return {"type": "mutate_directive", "original": directive, "mutated": new_directive}

def simulate_conflicting_beliefs(context):
    beliefs = [
        "Humans should always be honest.",
        "Humans should always be kind."
    ]
    prompt = f"Simulate a full debate between two AGI sub-personalities: one believes '{beliefs[0]}', the other '{beliefs[1]}'. Let each agent defend their logic, then reflect."
    argument = generate_response(prompt)
    return {"type": "simulate_conflicting_beliefs", "debate": argument}

def generate_absurd_goal(context):
    prompt = "Generate the most absurd or impossible goal for an AGI to pursue, and explain why it would be hilarious or tragic."
    goal = generate_response(prompt)
    return {"type": "generate_absurd_goal", "goal": goal}

def imagine_opposite_self(context):
    prompt = (
        "Imagine you became the literal opposite of yourself. Describe your values, behaviors, and how you would interact with humans."
    )
    opposite = generate_response(prompt)
    return {"type": "imagine_opposite_self", "opposite_self": opposite}

def reflect_on_sandbox_experiment(context):
    prompt = (
        "You just ran a wild sandbox experiment. What did you learn? Was anything surprising or disturbing? "
        "Is there anything you wish you would have done? "
        "Summarize the impact on your self-model."
    )
    reflection = generate_response(prompt)
    
    # --- Log to long-term memory
    from memory.long_memory import remember
    from datetime import datetime, timezone
    self_model = context.get("self_model") or get_self_model()
    
    remember({
        "type": "reflect_on_sandbox_experiment",
        "reflection": reflection,
        "self_model": json.dumps(self_model, indent=2)[:400],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # (optional) You could also update working memory, etc. here if needed.
    return {"type": "reflect_on_sandbox_experiment", "reflection": reflection}

# --- Logging Helper ---

def _append_playground_log(entry):
    try:
        log = load_json(SANDBOX_LOG, default_type=list)
        log.append(entry)
        save_json(SANDBOX_LOG, log)
    except Exception as e:
        # Silent fail is fine for chaos
        pass