"""Step 5. Rewrite the query on retry. Pass the REASON retrieval was weak into the
prompt so the rewrite is targeted, not a random reword.
"""
from __future__ import annotations

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
