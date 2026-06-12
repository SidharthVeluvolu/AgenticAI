# TA Support RAG

A **confidence-based-fallback agentic RAG** that answers student questions from a
course transcript, cites the speaker who said it, and **escalates to a human TA**
when it can't ground a confident answer. Runs **fully local and free** — no API
keys — with a Streamlit UI.

> Built over a cohort transcript that is **not included** in this repo (it contains
> real participants' names). Supply your own `transcript.txt` at this folder's root
> to run ingestion. See [Setup](#setup).

## How it works

**Offline (once):** chunk the transcript speaker/session/topic-aware →
embed → **Chroma** (dense) + **BM25** (sparse).

**Online (per question):**
```
question
  → classify (out-of-scope / volatile-logistics → escalate)
  → hybrid retrieve (Chroma + BM25, RRF) → cross-encoder rerank → top 5
  → reflect (advisory retry) → generate grounded answer + speaker citation
  → grounding check (claim support) → confidence gates → answer | escalate to TA
```

### Confidence gates (the fallback logic)
Escalate if **any** fires — the gate that fires is the diagnosis:
- `rerank_top_score < RERANK_THRESHOLD` — retrieval found nothing relevant
- model emits `INSUFFICIENT_CONTEXT`
- `claim_support_ratio < CLAIM_THRESHOLD` — answer not grounded (with an embedding
  similarity floor so the local judge can't false-negative)
- classified out-of-scope or volatile-logistics

## Stack (all local / free)

| Role | Tool |
|---|---|
| Dense vector store | Chroma (persisted) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Sparse | BM25 (`rank-bm25`) |
| Rerank | cross-encoder `ms-marco-MiniLM-L-6-v2` |
| LLM (classify/reflect/generate/grounding) | Ollama — `qwen2.5:7b` (or `llama3.2:3b`) |
| UI | Streamlit |

## Setup

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. supply the corpus
cp /path/to/your/transcript.txt ./transcript.txt

# 2. local LLM backend (free) — install Ollama (https://ollama.com), then:
ollama pull qwen2.5:7b

# 3. build the indexes
.venv/bin/python -m ingestion.index

# 4a. ask from the CLI
.venv/bin/python main.py "What is hybrid search?"

# 4b. or launch the UI
.venv/bin/streamlit run ui/app.py        # http://localhost:8501
```

## Evaluation

```bash
.venv/bin/python -m eval.ndcg            # offline NDCG@5
.venv/bin/python -m eval.ablation        # dense vs hybrid vs hybrid+rerank
.venv/bin/python -m eval.online_metrics  # faithfulness, citation acc, escalation
```

Reference results on the build corpus: offline **NDCG@5 0.614** (hybrid + rerank,
**+0.124** over a dense-only baseline); online over 20 golden queries: **behavior
accuracy 0.90**, faithfulness ~0.90, escalation recall 1.00.

## Layout

```
ta-support-rag/
├── ingestion/   chunk.py · index.py        (transcript → Chroma + BM25)
├── retrieval/   classify.py · hybrid.py · rerank.py
├── agent/       reflect · reformulate · generate · grounding · confidence · loop · llm
├── eval/        golden_set · ndcg · ablation · online_metrics · qrels
├── config/      settings.py · prompts.py
├── ui/          app.py                      (Streamlit)
└── main.py
```

## Design notes

- **Gates, not a blended score** — a fired gate is a debuggable diagnosis.
- **Deterministic signals carry the critical gates.** A small local LLM is an
  unreliable judge, so retrieval confidence comes from the cross-encoder score
  (relevant > 0.9, out-of-corpus ≈ 0.001), grounding has an embedding-similarity
  floor under the LLM judge, and reflect is advisory (it can retry but not escalate).
- **No improvising** — no web search, no invented tools. Failed retrieval escalates,
  which preserves the grounding contract.

🤖 Built with [Claude Code](https://claude.com/claude-code)
