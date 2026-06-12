"""Step 5. Rewrite the query on retry. Pass the REASON retrieval was weak into the
prompt so the rewrite is targeted, not a random reword.
"""
from __future__ import annotations

import re

from config import settings
from agent.llm import chat

_SYS = (
    "You rewrite a student's question into a better search query for a course-"
    "transcript knowledge base. Preserve the original meaning, but make it more "
    "retrievable: prefer the concept's canonical terms, drop chatty filler. "
    "Return ONLY the rewritten query, no preamble, no quotes."
)


def reformulate(query: str, reason: str) -> str:
    user = f"Original question: {query}\nWhy retrieval was weak: {reason}\nRewritten query:"
    out = chat(settings.REFLECT_MODEL, _SYS, user, temperature=0.2)
    return out.strip().strip('"').strip() or query


_CONCEPT_SYS = (
    "Extract the core topic(s) a student's question is about, for searching a course "
    "transcript. Return ONLY the key noun concept(s) as a short phrase — drop question "
    "words and instruction words like 'summarize', 'explain', 'how', 'why', and any "
    "framing about other topics. Examples:\n"
    "'What is chunking? Summarize how it improves retrieval in RAG?' -> chunking\n"
    "'How does BM25 differ from dense vector search?' -> BM25 dense vector search\n"
    "'Explain reranking and why it matters' -> reranking"
)


def extract_concepts(query: str) -> str:
    """Reduce a verbose/compound question to its core search concept(s). Used by the
    grounding-driven retry, where framing words pulled retrieval off the topic.

    Uses the STRONG model: extraction/structured rewriting is unreliable on the small
    model. Only runs on the failure path, so the extra cost is rare."""
    out = chat(settings.GENERATE_MODEL, _CONCEPT_SYS, f"Question: {query}\nConcepts:",
               temperature=0.0)
    return out.strip().strip('"').strip() or query


_EXPAND_SYS = (
    "A student asked a BROAD question about an AI course. List 3-4 specific sub-topics "
    "the course covers that together answer it, each as a short search phrase — e.g. "
    "hybrid search, reranking, chunking, metadata filtering, reducing hallucination, "
    "embeddings, evaluation. Return ONLY a JSON array of short strings."
)


def expand_queries(query: str, n: int = 4) -> list:
    """Decompose a broad question into specific sub-topic search phrases for a
    multi-query fan-out. Returns [] on failure (caller falls back to single query)."""
    import json
    try:
        # strong model — the small one can't produce parseable sub-topic JSON
        raw = chat(settings.GENERATE_MODEL, _EXPAND_SYS,
                   f"Question: {query}\nSub-topics (JSON array):",
                   json_mode=True, temperature=0.2)
        data = json.loads(raw)
    except Exception:
        return []
    # qwen may return a JSON array, {"topics": [...]}, or a dict whose KEYS are the
    # topics (values like "#1"). Handle all three.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        listval = next((v for v in data.values() if isinstance(v, list)), None)
        items = listval if listval is not None else list(data.keys())
    else:
        items = []
    out = []
    for x in items:
        s = str(x).replace("_", " ").strip()
        if s and not re.fullmatch(r"#?\d+", s):
            out.append(s)
    return out[:n]
