import numpy as np
from typing import Any, Dict, List, Sequence, Optional, Tuple
from utils.json_utils import load_json, save_json
from utils.embedder import get_embedding
from paths import KNOWLEDGE, WORKING_MEMORY_FILE, LONG_MEMORY_FILE

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    v1 = np.asarray(vec1, dtype=float).ravel()
    v2 = np.asarray(vec2, dtype=float).ravel()
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))

def _to_1d(v: Any) -> np.ndarray:
    """Coerce list/array/nested list to flat 1D float array."""
    a = np.asarray(v, dtype=float)
    if a.ndim == 2 and a.shape[0] == 1:
        a = a[0]
    return a.ravel()

def recall_relevant_knowledge(
    context: Any = "",
    long_memory: Optional[List[Dict[str, Any]]] = None,
    working_memory: Optional[List[Dict[str, Any]]] = None,
    max_items: int = 8,
) -> List[Dict[str, Any]]:
    """
    Return the most relevant memories (knowledge, working, long), sorted by semantic similarity to `context`.
    Increments `recall_count` on retrieved memories (and persists updates for working/long memories).
    """
    if not context:
        return []

    # Resolve context text(s)
    if isinstance(context, str):
        texts = [context]
    elif isinstance(context, Sequence) and all(isinstance(t, str) for t in context):
        texts = list(context) or [""]
    else:
        texts = [str(context)]

    # Embed the query; robust to single or multiple
    query_emb = get_embedding(texts)
    query_arr = np.asarray(query_emb, dtype=float)
    if query_arr.ndim == 1:
        context_emb = query_arr
    else:
        # average to single vector
        context_emb = query_arr.mean(axis=0)
    context_emb = _to_1d(context_emb)

    # Load sources (only from disk if not provided)
    kb: List[Dict[str, Any]] = load_json(KNOWLEDGE, default_type=list)

    wm_list: List[Dict[str, Any]] = (
        working_memory
        if isinstance(working_memory, list) else
        load_json(WORKING_MEMORY_FILE, default_type=list)
    )
    lm_list: List[Dict[str, Any]] = (
        long_memory
        if isinstance(long_memory, list) else
        load_json(LONG_MEMORY_FILE, default_type=list)
    )

    sources: List[Tuple[str, Dict[str, Any]]] = []
    for m in kb:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("knowledge", m))
    for m in wm_list:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("working", m))
    for m in lm_list:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("long", m))

    results: List[Tuple[float, Dict[str, Any], str]] = []
    for src_name, m in sources:
        emb = _to_1d(m.get("embedding", []))
        sim = cosine_similarity(context_emb, emb) if emb.size else 0.0

        importance = float(m.get("importance", 1))
        priority = float(m.get("priority", 1))
        recall_count = float(m.get("recall_count", 0))

        # lightweight scoring; drop constant time_bonus (or compute from timestamp if desired)
        score = sim + 0.15 * importance + 0.10 * priority + 0.07 * recall_count
        results.append((score, m, src_name))

    results.sort(key=lambda x: x[0], reverse=True)
    selected = results[: max(0, int(max_items))]

    # Increment recall_count on selected and persist where applicable
    wm_updated = False
    lm_updated = False
    for _, m, src in selected:
        try:
            m["recall_count"] = int(m.get("recall_count", 0)) + 1
            if src == "working":
                wm_updated = True
            elif src == "long":
                lm_updated = True
        except Exception:
            # keep going even if a record is oddly shaped
            continue

    if wm_updated:
        save_json(WORKING_MEMORY_FILE, wm_list)
    if lm_updated:
        save_json(LONG_MEMORY_FILE, lm_list)

    return [m for _, m, _ in selected]