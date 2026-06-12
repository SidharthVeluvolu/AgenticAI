"""Local Ollama chat client (free, no keys) + a tiny judgment cache + a context
formatter shared by the LLM steps.

README §8: cache the classify + reflect JUDGMENTS (not answers). A normalized-query
keyed dict is enough to start — that's the main latency lever for the loop.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from config import settings


def chat(model: str, system: str, user: str, temperature: float = 0.0,
         json_mode: bool = False, timeout: int = 240) -> str:
    """One-shot chat completion against local Ollama. Returns the message text."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        settings.OLLAMA_HOST + "/api/chat", data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Ollama call failed at {settings.OLLAMA_HOST}: {e}. "
            "Is `ollama serve` running and the model pulled?"
        ) from e


def format_context(docs) -> str:
    """Numbered excerpts, each tagged with its speaker — so the model can cite."""
    lines = []
    for i, d in enumerate(docs, 1):
        spk = (getattr(d, "metadata", {}) or {}).get("speaker", "Unknown")
        text = getattr(d, "page_content", str(d)).strip()
        lines.append(f"[{i}] ({spk}) {text}")
    return "\n\n".join(lines)


# ── judgment cache (classify + reflect) ──────────────────────────────────────
_CACHE: dict = {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def cached(namespace: str, key: str, compute):
    """Memoize a judgment by normalized key. compute() runs only on a miss."""
    ck = (namespace, _norm(key))
    if ck not in _CACHE:
        _CACHE[ck] = compute()
    return _CACHE[ck]
