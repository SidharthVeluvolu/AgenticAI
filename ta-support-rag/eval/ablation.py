"""Ablation: does each retrieval stage earn its keep?

Scores three configs on the SAME golden queries and SAME qrels, so the heuristic
labelling noise cancels and the deltas are the real signal (README Stage 2/3:
"get a baseline NDCG... compare to baseline"):
    dense-only     : Chroma similarity top-5
    hybrid         : EnsembleRetriever (dense + BM25, RRF) top-5, no rerank
    hybrid+rerank  : hybrid candidates -> cross-encoder rerank top-5

Run: python -m eval.ablation
"""
from __future__ import annotations

from eval.ndcg import ndcg_at_k, _key


def _run():
    from ingestion.chunk import load_transcript, chunk_transcript, _default_path
    from retrieval.hybrid import retrieve, _dense_store
    from retrieval.rerank import rerank
    from eval.golden_set import GOLDEN
    from eval.qrels import grade
    from config import settings

    k = settings.TOP_K_FINAL
    chunks = chunk_transcript(load_transcript(_default_path()))
    dense = _dense_store()

    totals = {"dense-only": 0.0, "hybrid": 0.0, "hybrid+rerank": 0.0}
    n = 0
    print(f"{'Q':<4}{'dense':>8}{'hybrid':>9}{'+rerank':>9}  query")
    for qid, q, behavior in GOLDEN:
        if behavior != "answer":
            continue
        relevance = {}
        for c in chunks:
            g = grade(c["content"], qid)
            if g:
                kk = _key(c["content"])
                relevance[kk] = max(relevance.get(kk, 0), g)
        if not relevance:
            continue

        d_docs = dense.similarity_search(q, k=k)
        h_docs = retrieve(q)
        r_docs = [doc for doc, _ in rerank(q, h_docs)]

        scores = {
            "dense-only": ndcg_at_k([_key(d.page_content) for d in d_docs], relevance, k),
            "hybrid": ndcg_at_k([_key(d.page_content) for d in h_docs], relevance, k),
            "hybrid+rerank": ndcg_at_k([_key(d.page_content) for d in r_docs], relevance, k),
        }
        for cfg, s in scores.items():
            totals[cfg] += s
        n += 1
        print(f"Q{qid:<3}{scores['dense-only']:>8.3f}{scores['hybrid']:>9.3f}"
              f"{scores['hybrid+rerank']:>9.3f}  {q[:42]}")

    print("\nmean NDCG@5:")
    base = totals["dense-only"] / n
    for cfg in ("dense-only", "hybrid", "hybrid+rerank"):
        mean = totals[cfg] / n
        delta = f"  ({'+' if mean >= base else ''}{mean - base:.3f} vs dense)" if cfg != "dense-only" else ""
        print(f"  {cfg:<14} {mean:.3f}{delta}")


if __name__ == "__main__":
    _run()
