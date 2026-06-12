"""Step 6. Claim-level grounding check (faithfulness) — the diagram's "Guardrails".

Split the answer into atomic claims; for each, ask the judge whether a retrieved
excerpt supports it (LLM-as-judge, binary yes/no). Return claim_support_ratio =
supported / total. Citations alone don't prove faithfulness — this does.
"""
from __future__ import annotations

import json
import re

from config import settings
from config.prompts import GROUNDING_SYSTEM_PROMPT
from agent.llm import chat, format_context


def _split_claims(answer: str) -> list:
    """Sentence-level claims. Drops the 'Sources:' line (which the model may place at
    the TOP or bottom) and speaker attributions ('— Aishwarya Srinivasan'), so a
    citation isn't judged as a claim — and front-loading the citation doesn't wipe
    the whole answer."""
    # remove any 'Sources:' citation line wherever it appears
    body = "\n".join(ln for ln in answer.splitlines()
                     if not re.match(r"\s*sources?\s*:", ln, re.IGNORECASE)).strip()
    # strip a leading "— Speaker Name" line
    body = re.sub(r"^[—\-]\s*[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}\s*[\n.]", "", body).strip()
    # strip a trailing "— Speaker Name" attribution
    body = re.sub(r"[—\-]\s*[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}\s*$", "", body).strip()
    parts = re.split(r"(?<=[.!?])\s+", body)
    return [p.strip() for p in parts
            if len(p.strip()) >= 20 and not re.match(r"^[—\-]", p.strip())]


def _cosine(a, b) -> float:
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    d = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a @ b / d)


def check_grounding(answer: str, citations: list, context: list) -> float:
    """Return supported_claims / total_claims in [0,1].

    A claim is supported if the LLM judge says yes OR its embedding is close to a
    retrieved chunk (deterministic floor under the local judge). All claims are
    judged in a SINGLE batched LLM call for latency.
    """
    claims = _split_claims(answer)
    if not claims:
        return 0.0
    ctx_docs = context[:settings.MAX_CONTEXT_CHUNKS]
    ctx = format_context(ctx_docs)

    # precompute chunk embeddings once (local, free)
    from retrieval.hybrid import _embeddings
    emb = _embeddings()
    chunk_vecs = emb.embed_documents([getattr(d, "page_content", str(d)) for d in ctx_docs])

    # one batched call judging every claim at once
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    user = (f"EXCERPTS:\n{ctx}\n\nCLAIMS:\n{numbered}\n\n"
            "For EACH numbered claim, decide if the excerpts support it. Return a JSON "
            'object mapping the claim number to "yes" or "no", e.g. {"1": "yes", "2": "no"}.')
    verdicts = {}
    try:
        data = json.loads(chat(settings.GROUNDING_MODEL, GROUNDING_SYSTEM_PROMPT, user,
                               json_mode=True))
        if isinstance(data, dict):
            for k, v in data.items():
                num = re.sub(r"\D", "", str(k))
                if num:
                    verdicts[int(num)] = str(v).strip().lower()
        elif isinstance(data, list):
            verdicts = {i + 1: str(v).strip().lower() for i, v in enumerate(data)}
    except Exception:
        verdicts = {}  # fall back to the embedding floor below

    supported = 0
    for i, claim in enumerate(claims, 1):
        if verdicts.get(i, "").startswith("y"):
            supported += 1
            continue
        cvec = emb.embed_query(claim)
        if max((_cosine(cvec, v) for v in chunk_vecs), default=0.0) >= settings.GROUNDING_SIM_THRESHOLD:
            supported += 1
    return supported / len(claims)
