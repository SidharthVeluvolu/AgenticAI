"""Step 5. Reflection: is the retrieved context enough to answer? CHEAP. CACHED.

Runs 2-3x per query, so it must be cheap and cached. Must conclude 'no' on the
FIRST pass when retrieval is clearly off-topic — don't reformulate three times on
an out-of-scope question.
"""
from __future__ import annotations

from config import settings
from config.prompts import REFLECT_SYSTEM_PROMPT
from agent.llm import chat, cached, format_context


def reflect(query: str, context: list) -> str:
    """Return 'yes' or 'no'."""
    ctx = format_context(context[:settings.TOP_K_FINAL])

    def _compute():
        user = (f"QUESTION:\n{query}\n\nRETRIEVED EXCERPTS:\n{ctx}\n\n"
                "Are these excerpts sufficient to answer the question faithfully? "
                "Answer yes or no.")
        out = chat(settings.REFLECT_MODEL, REFLECT_SYSTEM_PROMPT, user).strip().lower()
        return "yes" if out.startswith("y") else "no"

    return cached("reflect", query + "||" + ctx, _compute)
