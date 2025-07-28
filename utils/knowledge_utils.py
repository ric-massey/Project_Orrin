
import numpy as np
from utils.json_utils import load_json, save_json
from utils.embedder import get_embedding  # must exist; returns vector for a string
from paths import KNOWLEDGE, WORKING_MEMORY_FILE, LONG_MEMORY_FILE

def cosine_similarity(vec1, vec2):
    # Assumes both are numpy arrays
    if not np.any(vec1) or not np.any(vec2):
        return 0.0
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def recall_relevant_knowledge(context="", long_memory=None, working_memory=None, max_items=8):
    # If long_memory or working_memory are None, load from disk as fallback
    if long_memory is None:
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if working_memory is None:
        working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)
    """
    Returns most relevant memories (knowledge, working, long), sorted by semantic similarity to context.
    Increments recall_count on retrieved memories for biological realism.
    """
    if not context:
        return []

    # Ensure context is a list of strings for embedding
    if isinstance(context, str):
        texts = [context]
    elif isinstance(context, list) and all(isinstance(t, str) for t in context):
        texts = context
    else:
        texts = [str(context)]

    # Embed the query/context
    embeddings = get_embedding(texts)  # may return list of vectors
    context_emb = np.mean(np.array(embeddings), axis=0)  # average to single vector

    results = []

    # --- Load all memories ---
    sources = []
    # Knowledge
    kb = load_json(KNOWLEDGE, default_type=list)
    for m in kb:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("knowledge", m))
    # Working memory
    wm = load_json(WORKING_MEMORY_FILE, default_type=list)
    for m in wm:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("working", m))
    # Long memory
    lm = load_json(LONG_MEMORY_FILE, default_type=list)
    for m in lm:
        if isinstance(m, dict) and "embedding" in m:
            sources.append(("long", m))

    # --- Compute similarity and collect ---
    for source_name, m in sources:
        emb = np.array(m.get("embedding", []))
        if emb.shape == context_emb.shape and emb.shape[0] > 0:
            sim = cosine_similarity(context_emb, emb)
        else:
            sim = 0.0
        importance = float(m.get("importance", 1))
        priority = float(m.get("priority", 1))
        recall_count = float(m.get("recall_count", 0))
        time_bonus = 0.01  # optional recency boost

        score = sim + 0.15 * importance + 0.1 * priority + 0.07 * recall_count + time_bonus
        results.append((score, m, source_name))

    # --- Sort and select top N ---
    results = sorted(results, key=lambda x: -x[0])
    selected = results[:max_items]

    # --- Increment recall counts and save updated memories ---
    wm_updated, lm_updated = False, False
    for _, m, src in selected:
        m["recall_count"] = m.get("recall_count", 0) + 1
        if src == "working":
            wm_updated = True
        elif src == "long":
            lm_updated = True

    if wm_updated:
        save_json(WORKING_MEMORY_FILE, wm)
    if lm_updated:
        save_json(LONG_MEMORY_FILE, lm)

    # --- Return the full dicts, not just content ---
    recall_outputs = [m for _, m, _ in selected]

    return recall_outputs