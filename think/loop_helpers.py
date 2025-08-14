from __future__ import annotations
from typing import Any, Dict, Callable, Mapping, Tuple, List
import time
import json

from utils.log import log_model_issue
from utils.json_utils import load_json  # ⬅️ read-only
from paths import COGNITIVE_FUNCTIONS_LIST_FILE, BEHAVIORAL_FUNCTIONS_LIST_FILE

# Registries hold the real callables; we only FILTER by what's in the files.
from registry.cognition_registry import COGNITIVE_FUNCTIONS
from registry.behavior_registry import BEHAVIORAL_FUNCTIONS

# Behavior executor
from think.think_utils.action_gate import take_action

# Bandit + features
from think.bandit import contextual_bandit as bandit
from think.think_utils.select_function import extract_features  # NOTE: adds __bias__=1.0

Context = Dict[str, Any]
Registry = Dict[str, Callable[..., Any]]
Result = Dict[str, Any]


def emit_trace(**payload) -> None:
    """Append a single JSON line of telemetry to trace.jsonl (never crash)."""
    try:
        payload.setdefault("ts", time.time())
        with open("trace.jsonl", "a", encoding="utf-8") as _f:
            _f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as _e:
        log_model_issue(f"Trace emit failed: {_e}")


def compute_reward(result: Any, default_success: bool = False) -> float:
    """
    Map heterogeneous results to a simple reward for the bandit.
      - success True OR status == "ok" -> 1.0
      - warning/partial -> 0.5
      - explicit error/failure -> 0.0
    """
    if isinstance(result, Mapping):
        if result.get("success") is True or result.get("status") == "ok":
            return 1.0
        if result.get("warning") or result.get("partial"):
            return 0.5
        if "error" in result:
            return 0.0
        return 0.0
    if result is None and default_success:
        return 1.0
    return 0.0


def reason_string(result: Any, reward: float, feats: Any, tag: str) -> str:
    """Human-readable reason text for record_decision(). Robust to tuples/non-mappings."""
    if not isinstance(result, Mapping):
        if isinstance(result, tuple):
            result = {"data": list(result), "status": "tuple"}
        else:
            result = {"data": result}

    if result.get("reason"):
        return str(result["reason"])

    status = ""
    if "status" in result:
        status += f" status={result.get('status')!r}"
    if "error" in result:
        status += f" err={result.get('error')!r}"

    feat_hint = ""
    try:
        if isinstance(feats, Mapping):
            keys = list(feats.keys())[:3]
            if keys:
                feat_hint = " " + " ".join(f"{k}={feats[k]!r}" for k in keys)
        else:
            feat_hint = f" feats={type(feats).__name__}"
    except Exception:
        pass
    return f"{tag} reward={reward:.2f}{status}{feat_hint}".strip()


def _extract_callable_from_meta(meta: Any, name: str) -> Callable[..., Any] | None:
    """
    Strict extraction: accept either a callable, or a dict with a callable under 'function'.
    Everything else is logged and ignored.
    """
    if callable(meta):
        return meta
    if isinstance(meta, dict):
        fn = meta.get("function")
        if callable(fn):
            return fn
    if meta is not None:
        log_model_issue(f"Registry entry for '{name}' has invalid shape: {type(meta).__name__}")
    return None


def _load_name_list(path: str) -> List[str]:
    """Load a list of names from JSON; return [] on any problem. Accepts ['name', ...] or [{'name':..., ...}, ...]."""
    try:
        data = load_json(path, default_type=list)
        if not isinstance(data, list):
            return []
        out: List[str] = []
        for x in data:
            if isinstance(x, dict) and "name" in x:
                out.append(str(x["name"]))
            else:
                out.append(str(x))
        return out
    except Exception:
        return []


def names(src) -> List[str]:
    """
    Back-compat helper:
      - if src is a registry dict: return sorted keys
      - if src is a path (str/Path): read JSON list (strings or {name,...}) and return names
      - if src is a list: coerce items to names
    """
    # registry mapping
    if isinstance(src, dict):
        return sorted(src.keys())

    # persisted list path or in-memory list
    try:
        from pathlib import Path
        if isinstance(src, (str, Path)):
            data = load_json(src, default_type=list)
        else:
            data = src
    except Exception:
        data = []

    out: List[str] = []
    if isinstance(data, list):
        for x in data:
            if isinstance(x, dict) and "name" in x:
                out.append(str(x["name"]))
            else:
                out.append(str(x))
    return sorted(out)


def discover_callable_maps() -> Tuple[Registry, Registry]:
    """
    Read the persisted name lists (JSON) and return {name->callable} maps filtered to those names.
    ⚠️ This function is READ-ONLY with respect to the JSON files; it never writes.
    """
    wanted_cog = set(_load_name_list(COGNITIVE_FUNCTIONS_LIST_FILE))
    wanted_beh = set(_load_name_list(BEHAVIORAL_FUNCTIONS_LIST_FILE))

    cog_map: Registry = {}
    beh_map: Registry = {}

    # Filter cognition callables by persisted list
    if isinstance(COGNITIVE_FUNCTIONS, dict) and wanted_cog:
        for name in wanted_cog:
            meta = COGNITIVE_FUNCTIONS.get(name)
            fn = _extract_callable_from_meta(meta, name)
            if callable(fn):
                cog_map[name] = fn

    # Filter behavior callables by persisted list
    if isinstance(BEHAVIORAL_FUNCTIONS, dict) and wanted_beh:
        for name in wanted_beh:
            meta = BEHAVIORAL_FUNCTIONS.get(name)
            fn = _extract_callable_from_meta(meta, name)
            if callable(fn):
                beh_map[name] = fn

    return cog_map, beh_map


def _call_cognition(fn: Callable[..., Any], name: str, ctx: Context) -> Result:
    """
    Call cognition functions robustly:
      1) If ctx contains explicit __invoke_args / __invoke_kwargs, use them.
      2) Otherwise, auto-fill parameters by name from context (with a few synonyms).
      3) Otherwise, fall back to legacy attempts: fn(ctx), fn(event, ctx), fn(event, ctx, None), fn().
    Returns a dict result; never raises here.
    """
    try:
        import inspect  # local to avoid any import-cycle edge cases
    except Exception:
        inspect = None  # type: ignore

    # 0) Explicit args/kwargs provided by the selector/think()
    try:
        if isinstance(ctx.get("__invoke_args"), (list, tuple)) or isinstance(ctx.get("__invoke_kwargs"), dict):
            args = ctx.get("__invoke_args") or ()
            kwargs = ctx.get("__invoke_kwargs") or {}
            out = fn(*args, **kwargs)
            return out if isinstance(out, dict) else {"success": True, "data": out, "status": "ok"}
    except TypeError:
        # signature mismatch; proceed to smart kwargs / legacy attempts
        pass
    except Exception as e:
        return {"success": False, "error": str(e), "where": "cognition-call"}

    # 1) Smart keyword auto-fill from context (only if we can inspect the signature)
    if inspect is not None:
        try:
            sig = inspect.signature(fn)
            kw: Dict[str, Any] = {}
            missing_required: List[str] = []

            event = {"type": name, "name": name}

            # common synonyms to help match context keys to parameter names
            synonyms = {
                "tree": ["tree", "goal_tree", "plan_tree"],
                "updated": ["updated", "updated_goal", "goal_updated", "patch", "delta"],
                "goal": ["goal", "committed_goal", "active_goal"],
                "context": ["context", "ctx"],
            }

            def lookup_param(pname: str) -> Any:
                # direct
                if pname in ("ctx", "context"):
                    return ctx
                if pname == "event":
                    return event

                # exact in context
                if pname in ctx:
                    return ctx[pname]

                # look in common subdicts
                for key in ("committed_goal", "goal"):
                    sub = ctx.get(key)
                    if isinstance(sub, dict) and pname in sub:
                        return sub[pname]

                # synonym lookups
                for canon, keys in synonyms.items():
                    if pname == canon:
                        for k in keys:
                            if k in ctx:
                                return ctx[k]
                            for subkey in ("committed_goal", "goal"):
                                sub = ctx.get(subkey)
                                if isinstance(sub, dict) and k in sub:
                                    return sub[k]
                return None

            for p in sig.parameters.values():
                if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                    continue
                val = lookup_param(p.name)
                if val is not None:
                    kw[p.name] = val
                elif p.default is inspect._empty:
                    missing_required.append(p.name)

            if not missing_required:
                out = fn(**kw)
                return out if isinstance(out, dict) else {"success": True, "data": out, "status": "ok"}
        except Exception:
            # fall through to legacy attempts
            pass

    # 2) Legacy attempts (back-compat)
    for attempt in (
        lambda: fn(ctx),
        lambda: fn({"type": name, "name": name}, ctx),
        lambda: fn({"type": name, "name": name}, ctx, None),
        lambda: fn(),
    ):
        try:
            out = attempt()
            return out if isinstance(out, dict) else {"success": True, "data": out, "status": "ok"}
        except TypeError:
            continue
        except Exception as e:
            return {"success": False, "error": str(e), "where": "cognition-call"}

    return {"success": False, "error": "no_matching_signature", "where": "cognition-call"}


def execute_action_via_registries(
    action_name: str,
    ctx: Context,
    cog_reg: Registry,
) -> Result:
    """
    Execute a named action:
      - cognitive: call the function (try common signatures)
      - behavior: validate against persisted list, then execute via take_action
    Only accepts a string action_name; anything else is considered a caller bug.
    """
    if not isinstance(action_name, str) or not action_name:
        log_model_issue(f"Invalid selector type for execute_action_via_registries: {type(action_name).__name__}")
        return {"success": False, "error": "invalid selector", "where": "dispatch"}

    if not isinstance(ctx, dict):
        ctx = {}

    # Cognitive path (from provided cog_reg)
    fn = cog_reg.get(action_name)
    if callable(fn):
        return _call_cognition(fn, action_name, ctx)

    # Behavior path: validate by the persisted behavior name list only
    behavior_names = set(_load_name_list(BEHAVIORAL_FUNCTIONS_LIST_FILE))
    if action_name in behavior_names:
        try:
            ok = take_action({"type": action_name, "name": action_name}, ctx, ctx.get("speaker"))
            return {"success": bool(ok), "status": "ok" if ok else "fail"}
        except Exception as e:
            return {"success": False, "error": str(e), "where": "behavior-call"}

    return {"success": False, "error": f"Unknown action '{action_name}'", "where": "dispatch"}


def bandit_learn(
    tag: str,
    ctx: Context,
    reward: float,
    *,
    features: Dict[str, float] | None = None,
    decision_id: str | None = None
) -> Any:
    """
    Update the bandit with extracted features and the reward.
    Returns the features so callers can log them with record_decision.
    """
    feats = features or extract_features(ctx)
    try:
        bandit.update(tag, feats, reward)
        emit_trace(
            type="BANDIT_UPDATE",
            action=tag,
            reward=reward,
            decision_id=decision_id,
            features_on={k: v for k, v in feats.items() if v},
        )
    except AttributeError:
        # Legacy utils.bandit fallback (best-effort)
        try:
            from utils.context_key import context_key  # type: ignore
            from utils.bandit import record_outcome_ctx  # type: ignore
            record_outcome_ctx(context_key(ctx), tag, reward)
            emit_trace(type="BANDIT_UPDATE_FALLBACK", action=tag, reward=reward, decision_id=decision_id)
        except Exception as _e:
            emit_trace(
                type="BANDIT_UPDATE_FAILED",
                action=tag,
                reward=reward,
                decision_id=decision_id,
                error=str(_e),
            )
    return feats
