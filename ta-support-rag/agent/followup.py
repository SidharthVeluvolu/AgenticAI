"""Suggest follow-up questions a student might ask next, grounded in the same
course material. Cheap, cached — used by the UI after a successful answer.
"""
from __future__ import annotations

import json

from config import settings
from agent.llm import chat, cached

_SYS = (
    "A student asked a question about an AI course and got an answer. Propose 3 short, "
    "natural follow-up questions they might ask next, each answerable from the same "
    "course (retrieval, RAG, embeddings, models, chunking, evaluation, etc.). "
    "Return ONLY a JSON array of 3 strings."
)


def suggest_followups(query: str, answer: str, n: int = 3) -> list:
    def _compute():
        user = f"QUESTION: {query}\n\nANSWER: {answer[:600]}\n\nFollow-up questions (JSON array):"
        try:
            raw = chat(settings.REFLECT_MODEL, _SYS, user, json_mode=True, temperature=0.3)
            data = json.loads(raw)
            if isinstance(data, dict):  # some models wrap in {"questions": [...]}
                data = next((v for v in data.values() if isinstance(v, list)), [])
            return [str(x) for x in data][:n]
        except Exception:
            return []
    return cached("followup", query, _compute)
