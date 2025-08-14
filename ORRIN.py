# ORRIN.py
import os
from dotenv import load_dotenv
load_dotenv()  # ensure paths/registries read env-configured locations at import time
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import time
import traceback
from typing import Any, Dict
from datetime import datetime, timezone
import warnings  # added
import inspect   # NEW: for signature-based argument binding

# Silence HF Transformers clean_up_tokenization_spaces FutureWarning
warnings.filterwarnings(
    "ignore",
    message="`clean_up_tokenization_spaces` was not set.*",
    category=FutureWarning,
    module="transformers",
)

# === Core brain pieces ===
from think.think_module import think
from think.thalamus import process_inputs
from think.think_utils.action_gate import take_action

# === Helpers (keep this file lean) ===
from think.loop_helpers import (
    emit_trace,
    compute_reward,
    reason_string,
    names,
    discover_callable_maps,
    execute_action_via_registries,
    bandit_learn,
)

# === Registries (global caches + refresh) ===
from core.manager import load_custom_cognition
from registry.cognition_registry import COGNITIVE_FUNCTIONS, refresh as refresh_cog
from registry.behavior_registry import BEHAVIORAL_FUNCTIONS, refresh as refresh_beh

# === Emotions / reflection ===
from emotion.update_emotional_state import update_emotional_state
from emotion.reflect_on_emotions import reflect_on_emotions
from emotion.emotion_drift import check_emotion_drift

# === Planning & decisions ===
from cognition.planning.reflection import record_decision

# === Utils & I/O ===
from utils.get_cycle_count import get_cycle_count
from utils.load_utils import load_context
from utils.json_utils import load_json, save_json
from utils.log import log_error, log_private, log_activity, log_model_issue
from utils.emotion_utils import log_pain, log_uncertainty_spike

# === Error routing + repair (FIXED import) ===
from utils.error_router import route_exception
from cognition.repair.auto_repair import try_auto_repair  # <- fixed (singular "repair")

# === Paths ===
from paths import RELATIONSHIPS_FILE, MODEL_CONFIG_FILE, CONTEXT

Context = Dict[str, Any]

# --- Init Directories ---
for path in [RELATIONSHIPS_FILE, MODEL_CONFIG_FILE]:
    path.parent.mkdir(parents=True, exist_ok=True)

# --- Ensure LLM client is initialized centrally ---
# Importing this module triggers .env load + OpenAI client construction inside utils/generate_response.
try:
    from utils.generate_response import generate_response as _ensure_llm_client  # noqa: F401
except Exception as e:
    raise EnvironmentError(
        "❌ Failed to initialize LLM client via utils.generate_response. "
        "Check that OPENAI_API_KEY is set in your .env."
    ) from e

# --- Load Model Config (kept for your downstream use) ---
model_config = load_json(MODEL_CONFIG_FILE, default_type=dict)
selected = model_config.get(model_config.get("default", "thinking"), {})
model_name = selected.get("model", "gpt-4.1")
temperature = selected.get("temperature", 0.7)
max_tokens = selected.get("max_tokens", 32000)
system_prompt = selected.get("system_prompt", "")

# --- Build/refresh registries once at startup ---
try:
    refresh_cog()  # rebuild COGNITIVE_FUNCTIONS + persist names
except Exception as e:
    log_error(f"⚠️ Failed to refresh cognitive functions: {e}")

try:
    refresh_beh()  # rebuild BEHAVIORAL_FUNCTIONS + persist names
except Exception as e:
    log_error(f"⚠️ Failed to refresh behavioral functions: {e}")

# Merge user-defined cognition (shape-safe)
try:
    custom = load_custom_cognition()
    if isinstance(custom, dict):
        for k, v in custom.items():
            if callable(v):
                COGNITIVE_FUNCTIONS[k] = {"function": v, "is_cognition": True}
            elif isinstance(v, dict) and callable(v.get("function")):
                COGNITIVE_FUNCTIONS[k] = {
                    "function": v["function"],
                    "is_cognition": bool(v.get("is_cognition", True)),
                }
except Exception as e:
    log_error(f"⚠️ Failed to merge custom cognition: {e}")

# Callable maps (for cognition execution) and behavior name cache
COG_MAP, BEH_MAP = discover_callable_maps()
BEH_NAMES = set(names(BEHAVIORAL_FUNCTIONS))  # validate behavior actions quickly

# -------------------- NEW: context-aware cognition invoker --------------------
def _build_kwargs_for(fn, name: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Build kwargs from context by matching common parameter names."""
    try:
        sig = inspect.signature(fn)
    except Exception:
        return {}

    wm = ctx.get("working_memory", []) or []
    lm = ctx.get("long_memory", []) or []
    # recent: short tail of both memories
    try:
        recent = (wm[-6:] if isinstance(wm, list) else []) + (lm[-6:] if isinstance(lm, list) else [])
    except Exception:
        recent = []

    mapping = {
        "context": ctx, "ctx": ctx,
        "self_model": ctx.get("self_model"),
        "emotional_state": ctx.get("emotional_state", {}),
        "emotions": ctx.get("emotional_state", {}),
        "relationships": ctx.get("relationships", {}),
        "long_memory": lm,
        "working_memory": wm,
        "recent": recent,
        "recent_memories": recent,
        "speaker": ctx.get("speaker"),
        "goal": ctx.get("committed_goal") or ctx.get("focus_goal"),
        "focus_goal": ctx.get("focus_goal") or ctx.get("committed_goal"),
    }

    built = {}
    for p in sig.parameters.values():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if p.name in mapping and mapping[p.name] is not None:
            built[p.name] = mapping[p.name]
    return built

def _invoke_cognition(fn, name: str, ctx: Dict[str, Any], *, args=None, kwargs=None):
    """
    Prefer explicit args/kwargs if provided by think(); otherwise bind from context
    based on the function's signature. Try a few safe call shapes for back-compat.
    """
    # If think/selector supplied args/kwargs, trust them
    if isinstance(args, (list, tuple)) or isinstance(kwargs, dict):
        return fn(*(args or ()), **(kwargs or {}))

    built = _build_kwargs_for(fn, name, ctx)

    # Try a few common patterns
    for attempt in (
        lambda: fn(**built),
        lambda: fn(ctx),                                 # fn(context)
        lambda: fn({"type": name, "name": name}, ctx),   # fn(meta, context)
        lambda: fn(),                                    # bare call
    ):
        try:
            return attempt()
        except TypeError:
            continue  # try next signature
    # Final attempt (may raise)
    return fn(**built)
# ------------------------------------------------------------------------------

# --- Load context and RESET at startup ---
context = load_context()
context.setdefault("committed_goal", None)
context.setdefault("action_debt", 0)
context.setdefault("last_action_ts", 0.0)
context.setdefault("recent_picks", [])  # NEW: short history for boredom/novelty

# SMART RESET: decay moods; handle emergency recovery note
emotional_state = context.get("emotional_state", {})
emotional_state.setdefault("boredom", 0.0)  # NEW: ensure boredom exists at boot
for k in ["frustration", "pain", "anger", "fear", "boredom"]:
    if k in emotional_state:
        emotional_state[k] *= 0.65
        if emotional_state[k] < 0.07:
            emotional_state[k] = 0.0
context["emotional_state"] = emotional_state

from memory.working_memory import update_working_memory
if "emergency_action" in context:
    update_working_memory("🛑 Orrin is recovering from emergency shutdown. Residual uncertainty present.")
    emotional_state["uncertainty"] = min(emotional_state.get("uncertainty", 0.0) + 0.35, 1.0)
    context["emotional_state"] = emotional_state
    del context["emergency_action"]

if emotional_state.get("uncertainty", 0) > 0.2:
    update_working_memory("🤔 Waking up feeling uncertain after last shutdown. Self-reflection recommended.")
elif sum(emotional_state.get(k, 0.0) for k in ["frustration", "anger", "pain", "boredom"]) > 0.3:
    update_working_memory("😑 Residual negative mood detected from last session.")

# === Main Runtime Loop ===
if __name__ == "__main__":
    while True:
        try:
            print("thinking....")
            timestamp = datetime.now(timezone.utc).isoformat()
            log_activity(f"🫀 Starting cycle at {timestamp}")

            # Emotion update tick
            update_emotional_state()

            # Reload context fresh each cycle
            context = load_context()
            context.setdefault("committed_goal", None)
            context.setdefault("action_debt", 0)
            context.setdefault("last_action_ts", 0.0)
            context.setdefault("recent_picks", [])  # NEW: ensure present each loop

            emotional_state = context.get("emotional_state", {})
            emotional_state.setdefault("boredom", 0.0)  # NEW: ensure boredom exists each loop

            # Subtle mood decay each cycle
            for k in ["frustration", "pain", "anger", "fear", "boredom", "uncertainty"]:
                if k in emotional_state:
                    emotional_state[k] *= 0.92
                    if emotional_state[k] < 0.05:
                        emotional_state[k] = 0.0
            context["emotional_state"] = emotional_state

            # Reflex layer
            if emotional_state.get("emotional_stability", 1.0) < 0.6:
                reflect_on_emotions(context, context.get("self_model", {}), context.get("long_memory", []))

            # Thalamus: signal processing
            top_signals, attention_mode = process_inputs(context)
            context["top_signals"] = top_signals
            context["attention_mode"] = attention_mode

            # Fire alarm (emergency interrupt)
            if context.get("emergency_action"):
                emergency = context["emergency_action"]
                log_error(f"🔥 EMERGENCY ACTION TRIGGERED: {emergency.get('reason', str(emergency))}")
                log_private(f"🔥 EMERGENCY ACTION: {emergency}")
                print(f"🔥 EMERGENCY: {emergency.get('reason', str(emergency))}")
                break

            acted_this_cycle = False
            result = think(context)

            # Path A: think() produced a behavior action
            if isinstance(result, dict) and "action" in result:
                action = result["action"]
                speaker = context.get("speaker")
                action_type = action.get("type")

                if action_type not in BEH_NAMES:
                    log_error(f"⚠️ Unknown action type: {action_type}. Skipping action.")
                    log_model_issue(f"⚠️ Unknown action type attempted: {action_type}")
                    # Route as a soft incident & try repair
                    try:
                        route_exception(RuntimeError(f"Unknown action {action_type}"),
                                        phase="action", context=context, extra={"action": action_type})
                    except Exception:
                        pass
                    _ = try_auto_repair({"type": "UnknownAction",
                                         "msg": str(action_type),
                                         "trace": "",
                                         "phase": "action"}, context)
                    reward = 0.0
                    feats = bandit_learn(str(action_type or "unknown_action"), context, reward)
                    record_decision(str(action_type or "unknown_action"),
                                    reason_string({"error": "unknown_action"}, reward, feats, "think.action"))
                else:
                    try:
                        success = take_action(action, context, speaker)
                        acted_this_cycle = bool(success)
                        if success:
                            context["last_action_ts"] = time.time()
                            log_activity(f"🎤 Action Taken: {action_type}")
                        else:
                            log_error("⚠️ take_action returned False")
                            log_pain(context, "frustration", increment=0.3)
                        reward = 1.0 if success else 0.0
                        feats = bandit_learn(action_type, context, reward)
                        record_decision(action_type, reason_string({"success": success}, reward, feats, "think.action"))
                    except Exception as e:
                        route_exception(e, phase="action", context=context)
                        _ = try_auto_repair({"type": e.__class__.__name__,
                                             "msg": str(e),
                                             "trace": "",
                                             "phase": "action"}, context)
                        log_error(f"❌ Action execution failed: {e}")
                        log_pain(context, "frustration", increment=0.3)
                        reward = 0.0
                        feats = bandit_learn(str(action_type or "unknown_action"), context, reward)
                        record_decision(str(action_type or "unknown_action"),
                                        reason_string({"error": str(e)}, reward, feats, "think.action"))

            # Path B: think() produced a next_function (cognition function)
            elif isinstance(result, dict) and "next_function" in result:
                fn_name = result["next_function"]
                check_emotion_drift(max_cycles=10)

                meta_or_fn = COGNITIVE_FUNCTIONS.get(fn_name)
                fn = (meta_or_fn.get("function") if isinstance(meta_or_fn, dict) else meta_or_fn)

                try:
                    if callable(fn):
                        # NEW: invoke with args/kwargs if provided; else bind from context by signature
                        _invoke_cognition(
                            fn,
                            fn_name,
                            context,
                            args=result.get("args") if isinstance(result, dict) else None,
                            kwargs=result.get("kwargs") if isinstance(result, dict) else None,
                        )
                        log_activity(f"✅ Executed: {fn_name}")
                        reward = 1.0
                        feats = bandit_learn(fn_name, context, reward)
                        record_decision(fn_name, reason_string({"status": "ok"}, reward, feats, "think.fn"))
                    else:
                        log_model_issue(f"⚠️ Unknown function requested: {fn_name}")
                        try:
                            route_exception(RuntimeError(f"Unknown function {fn_name}"),
                                            phase="cognition", context=context, extra={"fn": fn_name})
                        except Exception:
                            pass
                        _ = try_auto_repair({"type": "UnknownFunction",
                                             "msg": str(fn_name),
                                             "trace": "",
                                             "phase": "cognition"}, context)
                        reward = 0.0
                        feats = bandit_learn(fn_name, context, reward)
                        record_decision(fn_name, reason_string({"error": "unknown_fn"}, reward, feats, "think.fn"))
                except Exception as e:
                    route_exception(e, phase="cognition", context=context, extra={"fn": fn_name})
                    _ = try_auto_repair({"type": e.__class__.__name__,
                                         "msg": str(e),
                                         "trace": "",
                                         "phase": "cognition"}, context)
                    log_error(f"❌ Function {fn_name} crashed: {e}")
                    log_private("⚠️ Pain signal: Function execution failed.")
                    log_pain(context, "frustration", increment=0.3 + 0.3 * emotional_state.get("anger", 0.4))
                    reward = 0.0
                    feats = bandit_learn(fn_name, context, reward)
                    record_decision(fn_name, reason_string({"error": str(e)}, reward, feats, "think.fn"))

            # Path C: robust fallback (selector + registries)
            else:
                log_model_issue("⚠️ No valid instruction returned by think(). Fallback to selector.")
                log_uncertainty_spike(context, increment=0.1)

                sel = None
                try:
                    from think.think_utils.select_function import select_function
                    sel = select_function(context)
                except Exception as _e:
                    log_model_issue(f"select_function failed: {_e}")

                if not sel or not isinstance(sel, str):
                    # Secondary fallback: self-reflection
                    fb_meta_or_fn = COGNITIVE_FUNCTIONS.get("reflect_on_self_beliefs")
                    fb_fn = (fb_meta_or_fn.get("function") if isinstance(fb_meta_or_fn, dict) else fb_meta_or_fn)
                    if callable(fb_fn):
                        try:
                            fb_fn()
                            log_activity("✅ Fallback executed: reflect_on_self_beliefs")
                            reward = 1.0
                        except Exception as e:
                            route_exception(e, phase="cognition", context=context, extra={"fn": "reflect_on_self_beliefs"})
                            _ = try_auto_repair({"type": e.__class__.__name__,
                                                 "msg": str(e),
                                                 "trace": "",
                                                 "phase": "cognition"}, context)
                            log_error(f"❌ Fallback function crashed: {e}")
                            reward = 0.0
                    else:
                        log_model_issue("No fallback function available.")
                        reward = 0.0
                    feats = bandit_learn("reflect_on_self_beliefs", context, reward)
                    record_decision("reflect_on_self_beliefs",
                                    reason_string({"status": "fallback"}, reward, feats, "fallback.fn"))
                else:
                    exec_result = execute_action_via_registries(sel, context, COG_MAP)
                    reward = compute_reward(exec_result)
                    feats = bandit_learn(sel, context, reward)
                    record_decision(sel, reason_string(exec_result, reward, feats, "fallback.sel"))
                    if isinstance(exec_result, dict) and exec_result.get("success"):
                        acted_this_cycle = True
                        context["last_action_ts"] = time.time()

            # ✅ Count any reflex actions taken inside action_gate this tick
            acted_this_cycle = acted_this_cycle or bool(context.pop("__acted_this_tick__", False))

            # Commit→Act guardrail accounting (only if a goal is committed)
            try:
                if context.get("committed_goal"):
                    context["action_debt"] = 0 if acted_this_cycle else int(context.get("action_debt", 0)) + 1
            except Exception as _e:
                log_model_issue(f"Guardrail accounting issue: {_e}")

            # Stall watchdog: minimum viable action if stuck
            try:
                STALL_SEC = 90
                now = time.time()
                if context.get("committed_goal"):
                    last_ts = float(context.get("last_action_ts", 0.0) or 0.0)
                    if (now - last_ts) > STALL_SEC:
                        goal = context.get("committed_goal") or {}
                        mv = goal.get("next_action")
                        if isinstance(mv, dict):
                            mv_type = mv.get("type")
                            if mv_type in BEH_NAMES:
                                try:
                                    ok = take_action(mv, context, context.get("speaker"))
                                    if ok:
                                        acted_this_cycle = True
                                        context["last_action_ts"] = time.time()
                                        context["action_debt"] = 0
                                        log_activity(f"🧭 Watchdog executed MV action: {mv_type}")
                                        feats = bandit_learn(mv_type, context, 1.0)
                                        record_decision(mv_type, "watchdog executed minimum viable action")
                                    else:
                                        log_model_issue("Watchdog tried MV action; take_action returned False.")
                                except Exception as _e:
                                    route_exception(_e, phase="action", context=context, extra={"mv_type": mv_type})
                                    _ = try_auto_repair({"type": _e.__class__.__name__,
                                                         "msg": str(_e),
                                                         "trace": "",
                                                         "phase": "action"}, context)
                                    log_model_issue(f"Watchdog MV action failed: {_e}")
                            else:
                                log_model_issue(f"Watchdog found MV action with unknown type: {mv_type}")
            except Exception as _e:
                log_model_issue(f"Watchdog error: {_e}")

            # Transparency trace
            try:
                chosen = None
                if isinstance(result, dict):
                    if "action" in result:
                        a = result["action"]; chosen = f"ACTION:{a.get('type','unknown')}"
                    elif "next_function" in result:
                        chosen = f"FN:{result.get('next_function')}"
                emit_trace(
                    chosen=chosen,
                    debt=context.get("action_debt", 0),
                    mode=context.get("mode"),
                    emotions=context.get("emotional_state", {}),
                    committed=bool(context.get("committed_goal")),
                    last_action_ts=context.get("last_action_ts"),
                )
            except Exception as _e:
                log_model_issue(f"Trace cycle emit failed: {_e}")

            # Persist context safely each cycle
            try:
                save_json(CONTEXT, context)
            except Exception as _e:
                log_model_issue(f"Context save failed: {_e}")

            # Single-cycle dev mode
            if os.getenv("ORRIN_ONCE") == "1":
                log_activity("Single-cycle mode; exiting after one tick.")
                break

            cycle_num = get_cycle_count()
            print(f"🔁 Orrin cycle {cycle_num} complete.\n")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\n🛑 Orrin loop stopped manually.")
            log_activity("Orrin loop manually interrupted by user.")
            break

        except Exception as e:
            route_exception(e, phase="loop", context=context)
            _ = try_auto_repair({"type": e.__class__.__name__,
                                 "msg": str(e),
                                 "trace": "",
                                 "phase": "loop"}, context)
            print(f"⚠️ Orrin crashed: {e}")
            traceback.print_exc()
            log_error(f"Main loop error: {e}")
            log_private("🔥 Top-level crash signal.")
            time.sleep(10)
