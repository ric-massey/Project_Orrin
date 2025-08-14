# goals_schema.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time
import json
import re


@dataclass
class AcceptanceCriteria:
    """
    success_predicate: mini-DSL, e.g.
      - 'stdout~="done" AND retries<=2'
      - 'flag==True OR (status=="ok")'
      - 'result>=0.9 AND completed'

    deadline_ts: epoch seconds; use has_expired() to check.
    retry_limit: cap for external orchestration logic (not enforced here).
    """
    success_predicate: str
    deadline_ts: Optional[float] = None  # epoch seconds (UTC)
    owner: str = "orrin"
    retry_limit: int = 2

    def validate(self) -> None:
        if not isinstance(self.success_predicate, str) or not self.success_predicate.strip():
            raise ValueError("success_predicate required")
        if self.retry_limit < 0:
            raise ValueError("retry_limit must be >= 0")

    def has_expired(self, now_ts: Optional[float] = None) -> bool:
        if self.deadline_ts is None:
            return False
        if now_ts is None:
            now_ts = time.time()
        return now_ts >= float(self.deadline_ts)


# -----------------------
# Predicate evaluation
# -----------------------

_OPS = ("<=", ">=", "==", "<", ">")

def _parse_literal(token: str) -> Any:
    """Parse numbers, booleans, null, or quoted strings; else return raw string."""
    t = token.strip()
    # Quoted string
    if (len(t) >= 2) and ((t[0] == t[-1] == '"') or (t[0] == t[-1] == "'")):
        return t[1:-1]
    # Try JSON (handles true/false/null/numbers)
    try:
        return json.loads(t)
    except Exception:
        return t

def _coerce(value: Any) -> Any:
    """Light normalization: strings 'true'/'false' -> bool; 'null' -> None; numeric-looking strings -> number."""
    if isinstance(value, str):
        low = value.strip().lower()
        if low == "true":
            return True
        if low == "false":
            return False
        if low in ("null", "none"):
            return None
        # numeric?
        try:
            if re.fullmatch(r"[+-]?\d+", low):
                return int(low)
            if re.fullmatch(r"[+-]?\d*\.\d+", low):
                return float(low)
        except Exception:
            pass
    return value

def _get_context_value(name: str, context: Dict[str, Any]) -> Any:
    """Fetch value from context; supports dotted keys like a.b.c."""
    name = name.strip()
    if not name:
        return None
    if "." in name:
        cur: Any = context
        for part in name.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
    return context.get(name)

def eval_predicate(expr: str, context: Dict[str, Any]) -> bool:
    """
    Very small, safe evaluator.
    Supported:
      - AND / OR (case-insensitive)
      - Comparisons: <=, >=, ==, <, >
      - Regex match: lhs~="pattern"   (Python re.search)
      - Bare key truthiness: e.g., completed
    Notes:
      - Parentheses are NOT supported.
      - Do not put AND/OR inside quoted strings.
    """
    if not isinstance(expr, str) or not expr.strip():
        return False

    # Split on AND/OR at top level (heuristic: assumes no AND/OR inside quotes)
    tokens = re.split(r'\s+(AND|OR)\s+', expr, flags=re.IGNORECASE)
    if not tokens:
        return False

    def eval_atom(atom: str) -> bool:
        atom = atom.strip()
        if not atom:
            return False

        # Regex match: lhs ~= "pattern"
        if "~=" in atom:
            lhs, pat = atom.split("~=", 1)
            left = _get_context_value(lhs, context)
            pattern = _parse_literal(pat)
            try:
                return re.search(str(pattern), str(left)) is not None
            except re.error:
                return False

        # Comparisons (check 2-char ops first)
        for op in _OPS:
            if op in atom:
                lhs, rhs = atom.split(op, 1)
                lv = _coerce(_get_context_value(lhs, context))
                rv_candidate = _parse_literal(rhs)
                # If rhs looks like an identifier (unquoted, not number/bool/null), try to resolve from context
                if isinstance(rv_candidate, str) and rv_candidate == rhs.strip():
                    resolved = _get_context_value(rv_candidate, context)
                    rv = _coerce(resolved if resolved is not None else rv_candidate)
                else:
                    rv = _coerce(rv_candidate)
                try:
                    if op == "==":
                        return lv == rv
                    elif op == "<":
                        return lv < rv
                    elif op == ">":
                        return lv > rv
                    elif op == "<=":
                        return lv <= rv
                    elif op == ">=":
                        return lv >= rv
                except Exception:
                    return False

        # Bare key truthiness
        return bool(_get_context_value(atom, context))

    # Fold left with AND/OR
    result = eval_atom(tokens[0])
    i = 1
    while i < len(tokens):
        op = tokens[i].upper()
        rhs = eval_atom(tokens[i + 1])
        if op == "AND":
            result = result and rhs
        else:
            result = result or rhs
        i += 2
    return bool(result)