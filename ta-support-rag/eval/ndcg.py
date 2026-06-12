"""Step 7. Offline NDCG@5 over the golden set.

Needs graded-relevance labels on chunks (2=directly answers, 1=related, 0=no) —
see eval/qrels.py. Queries 18-20 have an empty relevant set (escalate bucket);
correct retrieval there is 'nothing above threshold', scored by escalation
precision, not NDCG.

`ndcg_at_k` is the pure metric. Run `python -m eval.ndcg` to score the live
hybrid+rerank pipeline against the golden queries and print per-query + mean.
"""
from __future__ import annotations

import math


def _dcg(gains: list[float]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(retrieved: list, relevance: dict, k: int = 5) -> float:
    """NDCG@k for a ranked `retrieved` (list of doc keys) given `relevance`
    ({doc key -> grade}). Returns 0.0 when no relevant docs exist (IDCG = 0)."""
    gains = [relevance.get(key, 0) for key in retrieved[:k]]
    idcg = _dcg(sorted(relevance.values(), reverse=True)[:k])
    return _dcg(gains) / idcg if idcg > 0 else 0.0


# ── runner: score the live pipeline against the golden set ───────────────────
def _key(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _run():
    from ingestion.chunk import load_transcript, chunk_transcript, _default_path
    from retrieval.hybrid import retrieve
    from retrieval.rerank import rerank
    from eval.golden_set import GOLDEN
    from eval.qrels import grade
    from config import settings

    chunks = chunk_transcript(load_transcript(_default_path()))
    results = []
    for qid, q, behavior in GOLDEN:
        if behavior != "answer":
            continue
        relevance = {}
        for c in chunks:
            g = grade(c["content"], qid)
            if g:
                relevance[_key(c["content"])] = max(relevance.get(_key(c["content"]), 0), g)
        top = rerank(q, retrieve(q))
        retrieved = [_key(d.page_content) for d, _ in top]
        n = ndcg_at_k(retrieved, relevance, settings.TOP_K_FINAL)
        top_grade = relevance.get(retrieved[0], 0) if retrieved else 0
        results.append((qid, n, len(relevance), top_grade))
        flag = "" if relevance else "  <-- no labels (check qrels)"
        print(f"Q{qid:<2} NDCG@5={n:.3f}  rank1_grade={top_grade}  "
              f"relevant={len(relevance):<3}  {q[:46]}{flag}")

    labeled = [r for r in results if r[2] > 0]
    mean = sum(r[1] for r in labeled) / len(labeled) if labeled else 0.0
    print(f"\nmean NDCG@5 = {mean:.3f}  over {len(labeled)} grounded queries "
          f"(hybrid + cross-encoder rerank)")


if __name__ == "__main__":
    _run()
