"""Step 1. Speaker/topic/session-aware chunking of the transcript.

The transcript is conversational and concatenates several cohort sessions, each
opening with an "Audio Transcript" header. Within a session the format alternates:

    Speaker Name
    <a line of speech>
    HH:MM:SS
    <more speech>
    HH:MM:SS
    Next Speaker
    ...

Naive fixed-size splitting buries an explanation across chunk boundaries and loses
who said it. So we split on SPEAKER TURNS first (never merging two speakers into
one chunk), then size each turn with RecursiveCharacterTextSplitter only when a
single turn is longer than CHUNK_SIZE. Every chunk is tagged with session, speaker
and topic (architecture diagram: "session, speaker, topic").

VERIFY after building: run `python -m ingestion.chunk` and read the printed sample.
No single explanation should be split across speakers; the cited speaker must be
the one who actually said the chunk.
"""
from __future__ import annotations

import os
import re

from config import settings

# ── line classifiers ─────────────────────────────────────────────────────────
_TIMESTAMP = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
_SECTION = {"audio transcript", "chat messages"}
# A speaker header: 2–4 Capitalized-then-lowercase name tokens, optional
# "(The Gen Academy)" suffix. Each token must be [A-Z][a-z]+ (hyphen/apostrophe
# joins allowed), which rejects sentence fragments that happen to be capitalized
# ("Awesome. Yep.", "Germany. MediX") — those have internal periods / caps.
_SPEAKER = re.compile(
    r"^[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*"
    r"(?: [A-Z][a-z]+(?:[-'][A-Z][a-z]+)*){1,3}"
    r"(?: \(The Gen Academy\))?$"
)
# Lines that look like a name but are transcription noise, not real turns.
_NOT_SPEAKERS = {"Langchain Langraf", "Germany. MediX"}

# ── coarse topic tagging (keyword-first; refined later by retrieval/classify) ──
_TOPIC_KEYWORDS = {
    "retrieval-hybrid": ["bm25", "hybrid search", "dense retriev", "sparse",
                          "reciprocal", "rank fusion", "re-rank", "rerank", "top-k", "top k"],
    "evaluation": ["ndcg", " mrr", "precision", "recall", "faithful",
                   "reward hacking", "golden", "relevanc"],
    "chunking": ["chunk", "overlap", "splitting", "hierarchical chunk", "semantic chunk"],
    "embeddings-vectordb": ["embedding", "vector database", "vector db", "pinecone",
                            "cosine", "similarity search"],
    "rag-patterns": ["agentic rag", "graph rag", "retrieval augmented", "metadata filter",
                     "react loop", "reflect"],
    "models": ["temperature", "open source", "closed source", "parameter", "mixture of experts",
               "reasoning model", "trade-off", "context window", "context rot",
               "lost in the middle", "open weight", "closed weight"],
    "llm-fundamentals": ["transformer", "attention is all", "pre-train", "rlhf",
                         "reinforcement learning", "next word", "word2vec"],
    "tech-stack": ["hardware", "gpu", "tpu", "asic", "inference provider", "serving engine",
                   "observability", " mcp", "harness", "agentic framework", "routing platform"],
    "logistics": ["office hours", "certification", "maven", "discord", "guest lecture",
                  "credits", "week 2", "week 3", "intake form", "onboarding"],
}


def load_transcript(path: str) -> str:
    """Read the raw transcript file."""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _is_speaker(line: str) -> bool:
    if line in _NOT_SPEAKERS:
        return False
    if line.lower() in _SECTION:
        return False
    return bool(_SPEAKER.match(line))


def _normalize_speaker(name: str) -> str:
    return name.replace(" (The Gen Academy)", "").strip()


def detect_topic(text: str) -> str:
    """First topic whose keywords appear most in the text; 'general' if none."""
    low = text.lower()
    best, best_hits = "general", 0
    for topic, kws in _TOPIC_KEYWORDS.items():
        hits = sum(low.count(kw) for kw in kws)
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def parse_turns(text: str) -> list[dict]:
    """Split the raw transcript into speaker turns across all sessions.

    Returns dicts: {session, speaker, text, start_ts}. Section/timestamp lines are
    dropped from the body; the first timestamp of a turn is kept as start_ts.
    """
    turns: list[dict] = []
    session = 0
    cur = None  # active turn

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower() == "audio transcript":
            session += 1
            cur = None
            continue
        if line.lower() == "chat messages":
            continue
        if _TIMESTAMP.match(line):
            if cur is not None and cur["start_ts"] is None:
                cur["start_ts"] = line
            continue
        if _is_speaker(line):
            cur = {"session": max(session, 1), "speaker": _normalize_speaker(line),
                   "text": "", "start_ts": None}
            turns.append(cur)
            continue
        # content line
        if cur is None:  # speech before any speaker header (rare); open a stub turn
            cur = {"session": max(session, 1), "speaker": "Unknown",
                   "text": "", "start_ts": None}
            turns.append(cur)
        cur["text"] = (cur["text"] + " " + line).strip()

    return [t for t in turns if t["text"]]


def _splitter():
    """RecursiveCharacterTextSplitter if langchain is available, else a small
    stdlib fallback so chunking/verification runs without the full dep tree."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", ". ", "? ", "! ", " ", ""],
        ).split_text
    except Exception:
        def _fallback(t: str) -> list[str]:
            size, overlap = settings.CHUNK_SIZE, settings.CHUNK_OVERLAP
            if len(t) <= size:
                return [t]
            out, i = [], 0
            while i < len(t):
                out.append(t[i:i + size])
                i += size - overlap
            return out
        return _fallback


def chunk_transcript(text: str) -> list[dict]:
    """Return [{content, metadata:{session, speaker, topic, start_ts, turn_part}}].

    One chunk per speaker turn; long turns are sub-split but never merged with a
    neighbouring speaker's turn.
    """
    split = _splitter()
    chunks: list[dict] = []
    for turn in parse_turns(text):
        topic = detect_topic(turn["text"])
        pieces = split(turn["text"])
        for idx, piece in enumerate(pieces):
            chunks.append({
                "content": piece,
                "metadata": {
                    "session": turn["session"],
                    "speaker": turn["speaker"],
                    "topic": topic,
                    "start_ts": turn["start_ts"],
                    "turn_part": idx,
                },
            })
    return chunks


def _default_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "transcript.txt"),
                 os.path.join(here, "..", "..", "transcript.txt")):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return os.path.abspath(os.path.join(here, "..", "transcript.txt"))


if __name__ == "__main__":
    path = _default_path()
    text = load_transcript(path)
    chunks = chunk_transcript(text)

    from collections import Counter
    spk = Counter(c["metadata"]["speaker"] for c in chunks)
    top = Counter(c["metadata"]["topic"] for c in chunks)
    sess = Counter(c["metadata"]["session"] for c in chunks)
    lens = [len(c["content"]) for c in chunks]

    print(f"transcript: {path}")
    print(f"chunks: {len(chunks)} | sessions: {dict(sorted(sess.items()))}")
    print(f"chunk length: min={min(lens)} max={max(lens)} avg={sum(lens)//len(lens)}")
    print(f"top speakers: {spk.most_common(5)}")
    print(f"topics: {top.most_common()}")
    print("\n── sample chunks (verify speaker-whole, correctly attributed) ──")
    shown = 0
    for c in chunks:
        m = c["metadata"]
        if m["speaker"] in ("Aishwarya Srinivasan", "Arvind Narayanamurthy") and \
           m["topic"] in ("retrieval-hybrid", "evaluation", "chunking") and \
           len(c["content"]) > 200:
            print(f"\n[s{m['session']} · {m['speaker']} · {m['topic']} · {m['start_ts']}]")
            print(c["content"][:320].strip() + ("…" if len(c["content"]) > 320 else ""))
            shown += 1
            if shown >= 4:
                break
