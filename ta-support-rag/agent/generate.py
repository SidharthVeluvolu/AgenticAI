"""Step 5/6. Generate a grounded answer with speaker citations.

README locks `create_agent` with bound tools. Running a small LOCAL model, reliable
tool-calling isn't a safe bet, so we use the equivalent grounded-generation form:
the top-5 reranked excerpts (already the "semantic tool search" result) are placed
in context, each tagged with its speaker, and the TA system prompt enforces the
grounding contract — answer only from context, cite speaker, or emit
INSUFFICIENT_CONTEXT. The agentic behaviour (reflect/retry) lives in loop.py.
Cite speaker only; never invent tools or search the web — failed retrieval escalates.
"""
from __future__ import annotations

import re

from config import settings
from config.prompts import TA_SYSTEM_PROMPT
from agent.llm import chat, format_context


def _extract_citations(answer: str, context: list) -> list:
    """Ground citations in the ACTUAL speaker metadata of the retrieved chunks.

    The model's 'Sources:' line is unreliable (placeholders, 'Unknown', hallucinated
    or student names), so we only accept a cited name if it matches a real speaker of
    a context chunk; otherwise fall back to the named speakers in the context.
    """
    ctx_speakers = []
    for d in context:
        s = (getattr(d, "metadata", {}) or {}).get("speaker")
        if s and s != "Unknown" and s not in ctx_speakers:
            ctx_speakers.append(s)

    def _match(name):
        n = name.strip().strip("[]()<>").strip()
        if len(n) < 3 or not re.search(r"[A-Za-z]{3,}", n):
            return None
        first = n.split()[0].lower()
        for cs in ctx_speakers:
            if n.lower() in cs.lower() or cs.lower() in n.lower() or first in cs.lower():
                return cs
        return None

    cited = []
    m = re.search(r"sources?\s*:\s*(.+)$", answer, re.IGNORECASE | re.MULTILINE)
    if m:
        for raw in re.split(r"[,/;]|\band\b", m.group(1)):
            cs = _match(raw)
            if cs and cs not in cited:
                cited.append(cs)
    return (cited or ctx_speakers)[:3]


def generate(query: str, context: list) -> dict:
    """Return {answer, citations:[speaker,...], insufficient: bool}."""
    ctx = format_context(context[:settings.TOP_K_FINAL])
    user = (f"CONTEXT (numbered excerpts, each tagged with its speaker):\n{ctx}\n\n"
            f"STUDENT QUESTION: {query}")
    answer = chat(settings.GENERATE_MODEL, TA_SYSTEM_PROMPT, user, temperature=0.0)
    # space/underscore/punctuation-agnostic refusal detection
    norm = re.sub(r"[^A-Z]", "", answer.strip().upper())
    insufficient = norm.startswith("INSUFFICIENTCONTEXT")
    citations = [] if insufficient else _extract_citations(answer, context)
    return {"answer": answer.strip(), "citations": citations, "insufficient": insufficient}
