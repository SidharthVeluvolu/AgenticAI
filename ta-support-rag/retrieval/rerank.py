"""Step 3. Cross-encoder rerank -> top 5. LOW LATENCY (no LLM reranker).

The hybrid retriever returns ~20 candidates fused by RRF; the cross-encoder scores
each (query, chunk) pair jointly and reorders them, which is far more precise than
the first-pass embedding similarity. We keep the TOP_K_FINAL best.

The top reranked score is the retrieval-confidence signal for the first confidence
gate (escalate if rerank_top_score < RERANK_THRESHOLD). Raw cross-encoder outputs
are unbounded logits, so we squash them through a sigmoid to (0,1) — that makes
RERANK_THRESHOLD interpretable and stable across models.
"""
from __future__ import annotations

import math

from config import settings

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import CrossEncoder
        _MODEL = CrossEncoder(settings.RERANK_MODEL)
    return _MODEL


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, candidates: list, top_k: int | None = None) -> list:
    """Reorder candidate Documents by cross-encoder relevance to the query.

    Returns up to top_k items as (doc, score) tuples, score in (0,1), best first.
    The caller reads result[0][1] as rerank_top_score for the confidence gate.
    """
    if not candidates:
        return []
    top_k = top_k or settings.TOP_K_FINAL
    pairs = [(query, getattr(d, "page_content", str(d))) for d in candidates]
    raw = _model().predict(pairs)
    scored = sorted(
        ((doc, _sigmoid(float(s))) for doc, s in zip(candidates, raw)),
        key=lambda t: t[1],
        reverse=True,
    )
    return scored[:top_k]
