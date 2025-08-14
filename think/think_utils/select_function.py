# think/think_utils/select_function.py
from __future__ import annotations
from typing import Dict, List, Tuple, Union, Any
import uuid
import re

from paths import (
    COGNITIVE_FUNCTIONS_LIST_FILE,
    FOCUS_GOAL,
    EMOTIONAL_STATE_FILE,
    SELF_MODEL_FILE,    
    EMOTION_FUNCTION_MAP_FILE
)
from utils.json_utils import load_json
from utils.goals import extract_current_focus_goal
from think.bandit import contextual_bandit as bandit

FALLBACK_ACTIONS = ["reflect_on_directive", "plan_next_step", "summarize_memory"]


# -------------------- basic loaders (unchanged API) --------------------
def _load_actions() -> List[str]:
    items = load_json(COGNITIVE_FUNCTIONS_LIST_FILE, default_type=list)
    if not isinstance(items, list) or not items:
        return FALLBACK_ACTIONS
    names: List[str] = []
    for it in items:
        if isinstance(it, dict) and "name" in it:
            names.append(str(it["name"]))
        elif isinstance(it, str):
            names.append(it)
    return names or FALLBACK_ACTIONS


def _dominant_emotion() -> str:
    emo = load_json(EMOTIONAL_STATE_FILE, default_type=dict) or {}
    core = emo.get("core_emotions", {})
    if isinstance(core, dict) and core:
        try:
            return max(core.items(), key=lambda kv: kv[1])[0]
        except Exception:
            pass
    return str(emo.get("dominant", "neutral"))


def _focus_goal_name() -> str:
    fg = load_json(FOCUS_GOAL, default_type=dict) or {}
    try:
        s = extract_current_focus_goal(fg)
        if s:
            return str(s)
    except Exception:
        pass
    return str(fg.get("name", ""))


# -------------------- small helpers (additive) --------------------
def _tokenize(text: str) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    return re.findall(r"[a-z0-9]+", text.lower())


def _kw_overlap_score(candidate_text: str, ref_text: str) -> float:
    """soft keyword overlap in [0..1]. Works even if defs are short."""
    a = set(_tokenize(candidate_text))
    b = set(_tokenize(ref_text))
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = (len(a) ** 0.5) * (len(b) ** 0.5)
    return inter / denom if denom else 0.0


def _load_action_defs() -> Tuple[List[str], Dict[str, str]]:
    """
    Returns (names, defs). Supports:
      - ['name', ...]
      - [{'name': 'fn', 'definition': '...'}, ...]
    Falls back to using the name as the definition.
    """
    items = load_json(COGNITIVE_FUNCTIONS_LIST_FILE, default_type=list)
    if not isinstance(items, list) or not items:
        return (list(FALLBACK_ACTIONS), {n: n for n in FALLBACK_ACTIONS})

    names: List[str] = []
    defs: Dict[str, str] = {}
    for it in items:
        if isinstance(it, dict) and "name" in it:
            nm = str(it["name"])
            names.append(nm)
            defs[nm] = str(it.get("definition") or nm)
        elif isinstance(it, str):
            names.append(it)
            defs[it] = it

    if len(names) < 2:
        for fb in FALLBACK_ACTIONS:
            if fb not in names:
                names.append(fb)
                defs[fb] = fb
    return names, defs


def _get_directive_text() -> str:
    sm = load_json(SELF_MODEL_FILE, default_type=dict) or {}
    cd = sm.get("core_directive")
    if isinstance(cd, dict):
        return str(cd.get("statement", "")) or ""
    if isinstance(cd, str):
        return cd
    return ""


def _get_focus_goal_text() -> str:
    fg = load_json(FOCUS_GOAL, default_type=dict) or {}
    try:
        s = extract_current_focus_goal(fg)
        if s:
            return str(s)
    except Exception:
        pass
    name = str(fg.get("name", "") or "")
    desc = str(fg.get("description", "") or "")
    return (name + " " + desc).strip()


def _dominant_emotion_and_boredom() -> Tuple[str, float]:
    emo = load_json(EMOTIONAL_STATE_FILE, default_type=dict) or {}
    core = emo.get("core_emotions", {}) or {}
    boredom = float(core.get("boredom", emo.get("boredom", 0.0)) or 0.0)
    dom = None
    try:
        if isinstance(core, dict) and core:
            dom = max(core.items(), key=lambda kv: kv[1])[0]
    except Exception:
        dom = None
    return (dom or str(emo.get("dominant", "neutral"))), max(0.0, min(1.0, boredom))


def _recent_picks_from_ctx(ctx: Dict[str, Any]) -> List[str]:
    rp = ctx.get("recent_picks", [])
    return rp if isinstance(rp, list) else []


def _emotion_pref_scores_for_dominant(actions: List[str]) -> Dict[str, float]:
    """
    Use *only existing state* to bias functions by emotion:
    - First look inside EMOTIONAL_STATE_FILE:
        - emotion_function_map[dominant] / function_preferences[dominant] / emotion_function_weights[dominant]
    - Then (fallback) look inside EMOTION_FUNCTION_MAP_FILE if present.
    Normalizes to [0..1] with a floor, and handles singletons.
    """
    emo_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict) or {}
    dom = _dominant_emotion()
    candidates = (
        (emo_state.get("emotion_function_map") or {}),
        (emo_state.get("function_preferences") or {}),
        (emo_state.get("emotion_function_weights") or {}),
    )
    pref: Dict[str, float] = {}
    for block in candidates:
        if isinstance(block, dict) and isinstance(block.get(dom), dict):
            for fn, wt in block[dom].items():  # type: ignore[index]
                if fn in actions and isinstance(wt, (int, float)):
                    pref[fn] = float(wt)
            break

    # 🔁 fallback: dedicated map file produced by update_emotion_function_map(...)
    if not pref and EMOTION_FUNCTION_MAP_FILE:
        try:
            external_map = load_json(EMOTION_FUNCTION_MAP_FILE, default_type=dict) or {}
            block = external_map.get(dom)
            if isinstance(block, dict):
                for fn, wt in block.items():
                    if fn in actions and isinstance(wt, (int, float)):
                        pref[fn] = float(wt)
        except Exception:
            pass

    if not pref:
        return {}

    vals = list(pref.values())
    if len(vals) == 1:               # singleton → full weight
        k = next(iter(pref))
        return {k: 1.0}

    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return {k: 0.15 + 0.85 * ((v - lo) / span) for k, v in pref.items()}  # small floor so emo signal shows up




def _novelty_score(name: str, recent: List[str]) -> float:
    """
    High if not used recently or rarely used.
    Combines recency distance and inverse frequency within a window.
    """
    if not recent:
        return 1.0
    try:
        idx = len(recent) - 1 - recent[::-1].index(name)
        distance = len(recent) - 1 - idx
    except ValueError:
        distance = len(recent)  # never seen → maximum novelty

    window = recent[-32:]
    freq = window.count(name)
    # recency: farther back → higher
    r = min(1.0, distance / max(4.0, len(window) / 4.0))
    # frequency: fewer occurrences → higher
    f = 1.0 - min(1.0, (freq - 0.0) / max(1.0, len(window) / 3.0))
    return max(0.0, min(1.0, 0.6 * r + 0.4 * f))


def _bandit_pick_with_info(actions: List[str], feats: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
    """
    Try to get (picked, info) from the bandit; degrade gracefully to just a choice.
    `info` may contain 'scores', 'epsilon', etc., if supported by the bandit.
    """
    if hasattr(bandit, "choose"):
        # Prefer newer signature that can return scores
        try:
            picked, info = bandit.choose(actions, feats, return_scores=True)  # type: ignore
            if not isinstance(info, dict):
                info = {"_info": info}
            return picked, info
        except TypeError:
            res = bandit.choose(actions, feats)  # type: ignore
            if isinstance(res, tuple) and len(res) >= 2:
                return res[0], {"scores": res[1]}
            return res, {}
    if hasattr(bandit, "pick"):
        return bandit.pick(actions, feats), {}
    return (actions[0] if actions else ""), {}


def _bandit_hint_scores(actions: List[str], feats: Dict[str, float]) -> Dict[str, float]:
    """Normalize bandit scores to [0..1] for use as a hint (not the decider)."""
    chosen, info = _bandit_pick_with_info(actions, feats)
    scores = info.get("scores") if isinstance(info, dict) else None
    if not isinstance(scores, dict) or not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return {k: (v - lo) / span for k, v in scores.items()}


def _ensure_min_candidates(actions: List[str]) -> List[str]:
    """Guarantee at least 2 options to avoid collapsing into auto-select."""
    if len(actions) >= 2:
        return list(dict.fromkeys(actions))  # de-dupe preserve order
    seeded = list(dict.fromkeys([*actions, *FALLBACK_ACTIONS]))
    return seeded[:2] if len(seeded) >= 2 else seeded


# -------------------- public features (your original, unchanged) --------------------
def extract_features(context: Dict) -> Dict[str, float]:
    ctx = context or {}
    es = ctx.get("emotional_state", {}) or {}
    features: Dict[str, float] = {
        "bias_action": float(ctx.get("bias_action", 0.0) or 0.0),
        "pending_tools": float(len(ctx.get("pending_tools", []) or [])),
        "fatigue": float(es.get("fatigue", 0.0) or 0.0),
        "has_focus_goal": 1.0 if _focus_goal_name() else 0.0,
    }
    emo = _dominant_emotion()
    features[f"emo_{emo}"] = 1.0
    # Explicit intercept so the bandit can learn a baseline
    features["__bias__"] = 1.0
    return features


# -------------------- main selection (multi-factor) --------------------
def select_function(context: Dict, *args: Any, **kwargs: Any) -> Union[str, Tuple[str, Dict, bool]]:
    """
    Back-compat selector with multi-factor scoring (no new files):
      - Directive alignment (keyword overlap)
      - Focus-goal alignment (keyword overlap)
      - Emotion bias (if EMOTIONAL_STATE_FILE holds per-emotion fn weights)
      - Novelty/recency (rare & not recently used → higher)
      - Boredom boosts novelty weight
      - Bandit scores used as a hint (small weight), not the decider

    - New style: select_function(context) -> "fn_name"
    - Legacy: select_function(context, ...) -> (fn_name, reason, is_action)
    """
    # Candidates + definitions (if present in JSON)
    actions, defs = _load_action_defs()
    actions = _ensure_min_candidates(actions)

    feats = extract_features(context)

    # Legacy signals from kwargs (if present)
    if "amygdala_response" in kwargs:
        try:
            feats["amygdala_response"] = float(kwargs["amygdala_response"])
        except Exception:
            feats["amygdala_response"] = 0.0

    is_legacy = bool(args) or bool(kwargs)
    decision_id = str(uuid.uuid4())

    # Multi-factor data
    directive = _get_directive_text()
    focus_goal_text = _get_focus_goal_text()
    recent = _recent_picks_from_ctx(context)
    dominant, boredom = _dominant_emotion_and_boredom()
    emo_pref = _emotion_pref_scores_for_dominant(actions)
    band_hint = _bandit_hint_scores(actions, feats)

    # Weights (boredom increases novelty’s contribution)
    w_dir = 0.22
    w_goal = 0.22
    w_emo = 0.18
    base_w_novel = 0.23
    w_novel = min(0.45, base_w_novel * (1.0 + 1.5 * boredom))
    w_band = 0.15  # hint only

    # Score each action
    scored: List[Tuple[str, float, Dict[str, float]]] = []
    for name in actions:
        definition = defs.get(name, name)
        s_dir = _kw_overlap_score(definition, directive)
        s_goal = _kw_overlap_score(definition, focus_goal_text)
        s_emo = float(emo_pref.get(name, 0.0))
        s_nov = _novelty_score(name, recent)
        s_band = float(band_hint.get(name, 0.0))

        total = (w_dir * s_dir) + (w_goal * s_goal) + (w_emo * s_emo) + (w_novel * s_nov) + (w_band * s_band)
        scored.append((name, total, {"dir": s_dir, "goal": s_goal, "emo": s_emo, "novel": s_nov, "band": s_band}))

    scored.sort(key=lambda t: t[1], reverse=True)
    chosen = scored[0][0] if scored else (actions[0] if actions else "")

    # Optional tiny anti-repeat guard: only if immediate repeat and boredom is high
    override_applied = False
    immediate_repeat = False
    try:
        immediate_repeat = bool(recent and chosen == recent[-1])
        if actions and (immediate_repeat and boredom >= 0.6):
            alts = [a for a in actions if a != chosen]
            if alts:
                # pick most novel among alternatives
                alts_scored = [(a, _novelty_score(a, recent)) for a in alts]
                alts_scored.sort(key=lambda t: t[1], reverse=True)
                new_choice = alts_scored[0][0]
                if new_choice != chosen:
                    chosen = new_choice
                    override_applied = True
    except Exception:
        pass

    # Reason payload
    features_on = {k: v for k, v in feats.items() if isinstance(v, (int, float)) and abs(v) > 0}
    ranked = [(n, round(s, 4)) for n, s, _ in scored[:6]]
    comp = {n: cs for (n, _, cs) in scored[:6]}

    reason = {
        "via": "multi-factor",
        "weights": {"dir": w_dir, "goal": w_goal, "emo": w_emo, "novel": w_novel, "band": w_band},
        "features_on": features_on,
        "dominant_emotion": dominant,
        "boredom": boredom,
        "candidates": list(actions),
        "ranked": ranked,
        "component_scores": comp,
        "decision_id": decision_id,
        "anti_repeat": {
            "applied": override_applied,
            "boredom": boredom,
            "immediate_repeat": immediate_repeat,
        },
    }

    if is_legacy:
        return chosen, reason, False
    return chosen
