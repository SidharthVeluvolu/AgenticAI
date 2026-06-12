"""Central config. All thresholds and model choices live here so the eval loop
tunes one file. See README section 7."""

# ── LLM backend: local Ollama (free, no API keys) ────────────────────────────
# README §2 locked OpenAI tiering (classify/reflect cheap · generate expensive).
# Running locally, dollar-cost is ~0, so the tiering becomes a latency choice. We
# start with one small model across tiers; swap the cheap judges to a 1B for lower
# latency if the loop feels slow.
OLLAMA_HOST = "http://localhost:11434"
# Model tiering for latency: a fast small model handles the frequent judgment and
# query-rewriting steps; the stronger model handles the user-facing answer and the
# faithfulness gate (now a single batched call). Both stay resident in 16GB.
_CHEAP  = "llama3.2:3b"
_STRONG = "qwen2.5:7b"
CLASSIFY_MODEL  = _CHEAP   # every query (+ deterministic logistics keyword backstop)
REFLECT_MODEL   = _CHEAP   # advisory + reformulate/expand/extract — fast
GROUNDING_MODEL = _STRONG  # faithfulness gate — kept strong, but ONE batched call
GENERATE_MODEL  = _STRONG  # the answer

MAX_RETRIES = 3                  # also the escalation trigger when exhausted

RERANK_THRESHOLD = 0.3           # rerank top below this -> escalate (relevant>0.9, OOC~0.001)
CLAIM_THRESHOLD  = 0.5           # supported_claims / total below this -> escalate
                                 # (loosened from 0.7 — local judge is conservative)
# Grounding backstop: a claim also counts as supported if its embedding cosine to
# any retrieved chunk clears this — makes faithfulness robust to the noisy local
# LLM judge (which gives false 0.00s). Deterministic floor under the judge.
GROUNDING_SIM_THRESHOLD = 0.45   # grounded claims measured at 0.57+, refusals <0.31

TOP_K_RETRIEVE = 20
TOP_K_FINAL    = 5
RRF_WEIGHTS    = [0.5, 0.5]      # [dense, sparse]

# Cross-encoder reranker — local, free (sentence-transformers). Scores are passed
# through a sigmoid to (0,1) so RERANK_THRESHOLD is interpretable on that scale.
RERANK_MODEL   = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# Relevance floor: chunks scoring >= this are always kept in the final top-5 /
# passed to generation / shown as sources. Weak tail chunks (e.g. 40%) are dropped.
RERANK_KEEP_THRESHOLD = 0.70
# But broad questions (e.g. "what is RAG?") have relevant content spread across many
# mid-scoring conversational chunks. So if fewer than MIN_KEEP clear the floor, top
# up from the next-best chunks down to a SOFT floor — enough context, still no junk.
RERANK_MIN_KEEP   = 3
RERANK_SOFT_FLOOR = 0.50
# Broad "how-to" questions fan out into sub-topic queries and merge the union of
# relevant chunks (multi-query retrieval). Cap the merged context here, and let
# generation/grounding read up to MAX_CONTEXT_CHUNKS (broad answers need more).
MULTI_MAX_CHUNKS   = 8
MAX_CONTEXT_CHUNKS = 8

# ── Free / local stack (no paid API keys) ────────────────────────────────────
# README §2 locked Pinecone (dense) + OpenAI embeddings; swapped to a zero-cost
# local stack on request. Same shape — dense vector store + sparse BM25 — just
# running on the machine instead of a paid API.
EMBED_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"  # local, free, 384-dim
VECTOR_STORE = "chroma"           # local, persistent, supports metadata pre-filter
COLLECTION   = "ta-support"       # chroma collection name
import os as _os
_ROOT       = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
CHROMA_DIR  = _os.path.join(_ROOT, ".store", "chroma")   # dense index persists here
BM25_PATH   = _os.path.join(_ROOT, ".store", "bm25.pkl")  # sparse index persists here

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 100

# Chunk metadata tagged at ingestion (architecture diagram: "session, speaker, topic").
# Transcript concatenates multiple cohort sessions; session keeps them addressable
# and lets the pre-filter scope retrieval. Speaker drives the citation.
CHUNK_METADATA_FIELDS = ["session", "speaker", "topic"]
