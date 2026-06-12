"""Step 6. Claim-level grounding check (faithfulness) — the diagram's "Guardrails".

Split the answer into atomic claims; for each, ask the judge whether a retrieved
excerpt supports it (LLM-as-judge, binary yes/no). Return claim_support_ratio =
supported / total. Citations alone don't prove faithfulness — this does.
"""
from __future__ import annotations

import re

from config import settings
from config.prompts import GROUNDING_SYSTEM_PROMPT
from agent.llm import chat, format_context


def _split_claims(answer: str) -> list:
    """Sentence-level claims, dropping the trailing 'Sources:' line and fragments."""
    body = re.split(r"\n?sources?\s*:", answer, flags=re.IGNORECASE)[0]
    # strip leading citation dashes/markers like "— Arvind ..." and "[1]"
    body = re.sub(r"^[—\-\[\]\d() ]*", "", body.strip())
    parts = re.split(r"(?<=[.!?])\s+", body.strip())
    return [p.strip() for p in parts if len(p.strip()) > 15]


def _cosine(a, b) -> float:
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    d = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a @ b / d)


def check_grounding(answer: str, citations: list, context: list) -> float:
    """Return supported_claims / total_claims in [0,1].

    A claim is supported if the LLM judge says yes OR its embedding is close to a
    retrieved chunk (deterministic floor under the noisy local judge).
    """
    claims = _split_claims(answer)
    if not claims:
        return 0.0
    ctx_docs = context[:settings.TOP_K_FINAL]
    ctx = format_context(ctx_docs)

    # precompute chunk embeddings once (local, free)
    from retrieval.hybrid import _embeddings
    emb = _embeddings()
    chunk_vecs = emb.embed_documents([getattr(d, "page_content", str(d)) for d in ctx_docs])

    supported = 0
    for claim in claims:
        user = (f"EXCERPTS:\n{ctx}\n\nCLAIM: {claim}\n\n"
                "Do the excerpts support this claim? Answer yes or no.")
        out = chat(settings.GROUNDING_MODEL, GROUNDING_SYSTEM_PROMPT, user).strip().lower()
        if out.startswith("y"):
            supported += 1
            continue
        cvec = emb.embed_query(claim)
        if max((_cosine(cvec, v) for v in chunk_vecs), default=0.0) >= settings.GROUNDING_SIM_THRESHOLD:
            supported += 1
    return supported / len(claims)
