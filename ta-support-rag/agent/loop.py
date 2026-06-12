"""Step 5. Orchestrates the bounded agentic loop. Ties everything together.

classify -> pre-filter -> [retrieve -> rerank -> reflect -> (reformulate, retry)]
-> generate -> grounding -> confidence gates -> answer | escalate

Retries bounded to MAX_RETRIES. loop_count is logged per query (rising average =
weak retrieval). Out-of-scope escalates immediately; an empty pre-filter subset is
handled softly (drop the topic filter and retry before escalating), because our
topic tags are coarse and shouldn't starve a valid question.
"""
from __future__ import annotations

from config import settings
from retrieval.classify import classify_query, to_filter
from retrieval.hybrid import retrieve
from retrieval.rerank import rerank
from agent.reflect import reflect
from agent.reformulate import reformulate
from agent.generate import generate
from agent.grounding import check_grounding
from agent.confidence import should_escalate


def _result(escalated, reason, loop_count, **extra):
    base = {"answer": None, "citations": [], "escalated": escalated, "reason": reason,
            "loop_count": loop_count, "rerank_score": None, "claim_support_ratio": None,
            "sources": []}
    base.update(extra)
    return base


def _sources(reranked) -> list:
    """[(doc, score)] -> UI-friendly source rows."""
    out = []
    for doc, score in reranked:
        m = getattr(doc, "metadata", {}) or {}
        out.append({
            "speaker": m.get("speaker", "Unknown"),
            "session": m.get("session"),
            "topic": m.get("topic"),
            "timestamp": m.get("start_ts"),
            "score": round(float(score), 3),
            "text": getattr(doc, "page_content", str(doc)).strip(),
        })
    return out


def run(query: str) -> dict:
    cls = classify_query(query)
    # classify-time escalation: out-of-scope or volatile logistics — no durable
    # corpus answer exists, so don't burn the loop.
    if cls.get("escalate"):
        return _result(True, cls.get("reason") or "out_of_scope", 0, classification=cls)

    mfilter = to_filter(cls)
    q = query
    loop_count = 0
    best_score, best_docs, best_reranked = 0.0, [], []   # best context seen so far
    reflection = "no"

    for attempt in range(settings.MAX_RETRIES):
        loop_count += 1
        cands = retrieve(q, mfilter)
        reranked = rerank(q, cands)
        score = reranked[0][1] if reranked else 0.0
        # self-healing pre-filter: a wrong topic filter starves retrieval with
        # plenty of OFF-topic candidates that rerank near zero (not empty). Drop
        # the filter and retry unfiltered before judging — the classifier isn't
        # trusted enough to escalate a good query.
        if mfilter and score < settings.RERANK_THRESHOLD:
            mfilter = {}
            cands = retrieve(q, mfilter)
            reranked = rerank(q, cands)
            score = reranked[0][1] if reranked else 0.0
        docs = [d for d, _ in reranked]
        if score > best_score:
            best_score, best_docs, best_reranked = score, docs, reranked

        last_attempt = attempt == settings.MAX_RETRIES - 1

        # Gate: retrieval found nothing relevant. rerank is the RELIABLE signal
        # (relevant > 0.9, out-of-corpus ~ 0.001), so escalate only here.
        if score < settings.RERANK_THRESHOLD:
            if last_attempt:
                break
            q = reformulate(query, "top results scored below the relevance threshold")
            continue

        # reflect is ADVISORY: a weak local judge shouldn't escalate a strong-rerank
        # query. It can request one more reformulation, but on exhaustion we answer
        # from the best context — grounding is the real faithfulness gate.
        reflection = reflect(query, docs)
        if reflection == "yes" or last_attempt:
            break
        q = reformulate(query, "retrieved excerpts were judged insufficient to answer")

    sources = _sources(best_reranked)

    # never found relevant context across all attempts
    if best_score < settings.RERANK_THRESHOLD:
        return _result(True, f"low_rerank_score({best_score:.2f})", loop_count,
                       rerank_score=best_score, sources=sources)

    # generate + ground from the best context
    gen = generate(query, best_docs)
    if gen["insufficient"]:
        return _result(True, "model_insufficient_context", loop_count,
                       rerank_score=best_score, sources=sources)

    claim_ratio = check_grounding(gen["answer"], gen["citations"], best_docs)
    # reflection passed as "yes" — it must not drive the gate (it's advisory).
    escalate, reason = should_escalate(
        best_score, claim_ratio, out_of_scope=False, retries_exhausted=True,
        reflection="yes", insufficient=False,
    )
    if escalate:
        return _result(True, reason, loop_count, rerank_score=best_score,
                       claim_support_ratio=claim_ratio, sources=sources)

    return {"answer": gen["answer"], "citations": gen["citations"], "escalated": False,
            "reason": None, "loop_count": loop_count, "rerank_score": best_score,
            "claim_support_ratio": claim_ratio, "sources": sources}
