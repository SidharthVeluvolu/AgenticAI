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
import re

from agent.reflect import reflect
from agent.reformulate import reformulate, extract_concepts, expand_queries

# Broad, open-ended "how-to/ways-to" questions whose answer is spread across many
# techniques — these benefit from a multi-query fan-out, not a single query.
_BROAD_RE = re.compile(
    r"\b(how (to|do i|can i|do you|does one)\b.*\b(improve|better|optimi|reduce|"
    r"increase|enhance|fix|build|design)|ways to|best practices|tips (for|to)|"
    r"make .* better|what are (the )?(ways|techniques|methods|strategies|steps|"
    r"best practices|approaches))\b", re.IGNORECASE)
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


def _retrieve_rank_filter(q: str):
    """retrieve -> rerank -> apply relevance floor (+ backfill). Returns
    (top_score, kept_docs, kept_pairs)."""
    reranked = rerank(q, retrieve(q))
    score = reranked[0][1] if reranked else 0.0
    kept = [(d, s) for d, s in reranked if s >= settings.RERANK_KEEP_THRESHOLD]
    if len(kept) < settings.RERANK_MIN_KEEP:
        extra = [(d, s) for d, s in reranked
                 if settings.RERANK_SOFT_FLOOR <= s < settings.RERANK_KEEP_THRESHOLD]
        kept = kept + extra[: settings.RERANK_MIN_KEEP - len(kept)]
    return score, [d for d, _ in kept], kept


def _aspect_retrieve(query: str):
    """Multi-query fan-out for broad questions: expand to sub-topics, retrieve each
    independently (so each technique's chunks score high against its own query), and
    merge the union of relevant chunks. Returns (docs, pairs)."""
    merged = {}  # content -> (doc, score)
    for sq in [query] + expand_queries(query):
        _, _, kept = _retrieve_rank_filter(sq)
        for d, s in kept:
            k = d.page_content
            if k not in merged or s > merged[k][1]:
                merged[k] = (d, s)
    pairs = sorted(merged.values(), key=lambda t: t[1], reverse=True)[:settings.MULTI_MAX_CHUNKS]
    return [d for d, _ in pairs], pairs


def _generate_and_ground(query: str, docs: list):
    """Returns (gen_dict, claim_ratio | None if insufficient)."""
    gen = generate(query, docs)
    if gen["insufficient"]:
        return gen, None
    return gen, check_grounding(gen["answer"], gen["citations"], docs)


def run(query: str) -> dict:
    cls = classify_query(query)
    # classify-time escalation: out-of-scope or volatile logistics — no durable
    # corpus answer exists, so don't burn the loop.
    if cls.get("escalate"):
        return _result(True, cls.get("reason") or "out_of_scope", 0, classification=cls)

    # Topic pre-filter is DISABLED for retrieval. The coarse classifier-driven
    # filter measurably reduced recall on broad queries — e.g. "what is RAG?" got
    # scoped to one topic bucket and lost 5+ relevant chunks that score >0.9
    # unfiltered. Retrieval is strong unfiltered; classify is kept only for the
    # out-of-scope / volatile-logistics escalation gates above.
    q = query
    loop_count = 0
    best_score, best_docs, best_reranked = 0.0, [], []   # best context seen so far

    for attempt in range(settings.MAX_RETRIES):
        loop_count += 1
        score, docs, kept = _retrieve_rank_filter(q)
        if score > best_score:
            best_score, best_docs, best_reranked = score, docs, kept

        last_attempt = attempt == settings.MAX_RETRIES - 1

        # Gate: retrieval found nothing relevant. rerank is the RELIABLE signal
        # (relevant > 0.9, out-of-corpus ~ 0.001), so escalate only here.
        if score < settings.RERANK_THRESHOLD:
            if last_attempt:
                break
            q = reformulate(query, "top results scored below the relevance threshold")
            continue

        # High-confidence retrieval (top chunk clears the keep floor) — the rerank
        # score is reliable, so skip the advisory reflect LLM call entirely. This is
        # the common case and saves 1-3 model calls per query.
        if score >= settings.RERANK_KEEP_THRESHOLD or last_attempt:
            break
        # Borderline retrieval: reflect (advisory) decides whether to reformulate.
        if reflect(query, docs) == "yes":
            break
        q = reformulate(query, "retrieved excerpts were judged insufficient to answer")

    sources = _sources(best_reranked)

    # never found relevant context across all attempts
    if best_score < settings.RERANK_THRESHOLD:
        return _result(True, f"low_rerank_score({best_score:.2f})", loop_count,
                       rerank_score=best_score, sources=sources)

    # no chunk cleared the relevance floor — too weak to answer confidently
    if not best_docs:
        return _result(True, f"below_relevance_floor({best_score:.2f}<{settings.RERANK_KEEP_THRESHOLD})",
                       loop_count, rerank_score=best_score, sources=sources)

    # Broad how-to questions: a single query under-retrieves because the answer is
    # spread across many techniques. Fan out to sub-topics and merge for richer
    # context (only when the question is on-topic to begin with).
    if _BROAD_RE.search(query):
        a_docs, a_pairs = _aspect_retrieve(query)
        if len(a_docs) > len(best_docs):
            best_docs, best_reranked = a_docs, a_pairs
            best_score = a_pairs[0][1] if a_pairs else best_score
            sources = _sources(a_pairs)
            loop_count += 1

    # generate + ground from the best (>= floor) context
    gen, claim_ratio = _generate_and_ground(query, best_docs)

    # Grounding-driven retry: if the answer can't be grounded, retrieval likely
    # grabbed related-but-WRONG content — common on verbose/compound questions,
    # where framing words ("...summarize how it improves RAG") pull the reranker
    # off the core concept. Reformulate to the concept, retrieve again, and keep
    # whichever attempt grounds better — before escalating. Fires only on failure,
    # so it can't regress queries that already work.
    failed = gen["insufficient"] or (claim_ratio is not None
                                     and claim_ratio < settings.CLAIM_THRESHOLD)
    if failed:
        # reduce to the core concept (not a faithful rewrite) — framing words like
        # "...summarize how it improves RAG" are exactly what pulled retrieval off topic.
        fq = extract_concepts(query)
        s2, d2, k2 = _retrieve_rank_filter(fq)
        if d2 and s2 >= settings.RERANK_THRESHOLD:
            loop_count += 1
            gen2, ratio2 = _generate_and_ground(query, d2)
            base = -1.0 if gen["insufficient"] else claim_ratio
            cand = -1.0 if gen2["insufficient"] else ratio2
            if cand > base:   # keep the better-grounded attempt
                gen, claim_ratio = gen2, ratio2
                best_score, best_docs, best_reranked = s2, d2, k2
                sources = _sources(k2)

    if gen["insufficient"]:
        return _result(True, "model_insufficient_context", loop_count,
                       rerank_score=best_score, sources=sources)

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
