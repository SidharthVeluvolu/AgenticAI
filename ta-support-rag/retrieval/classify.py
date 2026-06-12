"""Step 4. Classify a query to metadata for pre-filtering. CHEAP model. CACHED.

Primary job in v1: flag clearly OUT-OF-SCOPE questions so the loop escalates them
without burning retries (the escalation probe, query 20). Secondary job: suggest a
topic to scope retrieval. Topic tags are coarse (keyword-derived at ingestion), so
the topic filter is applied SOFTLY by the loop — if it starves retrieval, the loop
drops it. That respects the README warning that a wrong filter starves retrieval.
"""
from __future__ import annotations

import json
import re

from config import settings
from config.prompts import CLASSIFY_SYSTEM_PROMPT
from agent.llm import chat, cached

TOPICS = ["retrieval-hybrid", "evaluation", "chunking", "embeddings-vectordb",
          "rag-patterns", "models", "llm-fundamentals", "tech-stack", "logistics"]

# Deterministic backstop for volatile-logistics questions the local classifier
# misses. These are time-sensitive facts a human must answer, not durable concepts.
# Note: avoid bare concept words like "mandatory" (appears in "why is hybrid search
# mandatory for production") — anchor on unambiguous logistics terms.
_LOGISTICS_RE = re.compile(
    r"\b(office hours|certification|certificate|deadline|due date|"
    r"when (is|are|will|do|does) .*(held|due|start|happen|session|class|office)|"
    r"what time|how many .*(project|assignment)s? (are )?(mandatory|required|due)|"
    r"enrol|prerequisite dates?)\b", re.IGNORECASE)


def classify_query(query: str) -> dict:
    """Return {topic, speaker, out_of_scope}."""
    def _compute():
        sys = CLASSIFY_SYSTEM_PROMPT.format(topics=TOPICS)
        try:
            raw = chat(settings.CLASSIFY_MODEL, sys, query, json_mode=True)
            data = json.loads(raw)
        except Exception:
            return {"topic": None, "speaker": None, "out_of_scope": False}
        topic = data.get("topic")
        out = (topic == "out_of_scope")
        volatile = (topic == "escalate_logistics") or bool(_LOGISTICS_RE.search(query))
        reason = "out_of_scope" if out else ("volatile_logistics" if volatile else None)
        return {
            "topic": None if topic not in TOPICS else topic,
            "speaker": data.get("speaker") or None,
            "out_of_scope": out,
            "escalate": out or volatile,   # classify-time escalation (no corpus answer)
            "reason": reason,
        }
    return cached("classify", query, _compute)


def to_filter(classification: dict) -> dict:
    """Build the metadata pre-filter from a classification (empty = no filter)."""
    f = {}
    if classification.get("topic"):
        f["topic"] = classification["topic"]
    if classification.get("speaker"):
        f["speaker"] = classification["speaker"]
    return f
