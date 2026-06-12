"""TA Support Bot — Streamlit UI.

Simple flow: ask a question -> grounded answer + author + confidence, or a clean
"refer to a human TA" card with the reason. Shows the source excerpts that were
discussed and suggests follow-up questions.

Run from the project root:
    cd ta-support-rag
    .venv/bin/streamlit run ui/app.py
(Requires the local Ollama server running — see README / project setup.)
"""
from __future__ import annotations

import os
import re
import sys

import streamlit as st

# allow `streamlit run ui/app.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.loop import run                      # noqa: E402
from agent.followup import suggest_followups    # noqa: E402

st.set_page_config(page_title="TA Support Bot", page_icon="🎓", layout="centered")

EXAMPLES = [
    "What is reciprocal rank fusion?",
    "What does a re-ranker do in the retrieval pipeline?",
    "What is the lost in the middle problem?",
    "What are the four trade-offs when picking a model?",
    "What are the three chunking strategies covered?",
    "When are office hours held?",
]

# friendly explanation for each escalation gate
ESCALATION_COPY = {
    "out_of_scope": ("Outside the course",
                     "This question isn't covered by the course material, so it's best answered by a human TA."),
    "volatile_logistics": ("Ask a TA — this changes over time",
                           "This is about schedules, deadlines, or certification details that change. A TA will give you the current, correct answer."),
    "low_rerank_score": ("No relevant material found",
                         "I couldn't find anything relevant in the course transcript for this. A TA can help."),
    "low_claim_support": ("Couldn't ground a confident answer",
                          "I found related material but couldn't fully ground an answer in it, so I'm not confident enough to answer. A TA can help."),
    "model_insufficient_context": ("Not enough context",
                                   "The retrieved material wasn't enough to answer this reliably. A TA can help."),
}


def _clean_answer(answer: str) -> str:
    """Strip the 'Sources:' line (top or bottom) and leading/trailing '— Speaker'
    attributions for display — the speaker is shown separately as a metric."""
    body = "\n".join(ln for ln in answer.splitlines()
                     if not re.match(r"\s*sources?\s*:", ln, re.IGNORECASE)).strip()
    body = re.sub(r"^[—\-]\s*[A-Z][\w .'-]+\s*\n+", "", body).strip()
    body = re.sub(r"\s*[—\-]\s*[A-Z][\w .'-]+\s*$", "", body).strip()
    return body


def _ask(query: str):
    st.session_state["pending"] = query


# ── header ───────────────────────────────────────────────────────────────────
st.title("🎓 TA Support Bot")
st.caption("Grounded answers from the Gen Academy cohort transcript — with the speaker who said it. "
           "When it can't ground a confident answer, it refers you to a human TA.")

with st.sidebar:
    st.subheader("Try asking")
    for ex in EXAMPLES:
        st.button(ex, key=f"ex_{ex}", use_container_width=True, on_click=_ask, args=(ex,))
    st.divider()
    st.caption("Local + free: Chroma · sentence-transformers · cross-encoder · Ollama. No data leaves your machine.")

# ── input ────────────────────────────────────────────────────────────────────
with st.form("ask_form", clear_on_submit=False):
    typed = st.text_input("Your question", placeholder="e.g. What is hybrid search?")
    submitted = st.form_submit_button("Ask", type="primary")
if submitted and typed.strip():
    _ask(typed.strip())

query = st.session_state.pop("pending", None)

# ── answer ───────────────────────────────────────────────────────────────────
if query:
    st.markdown(f"**Question:** {query}")
    with st.spinner("Searching the transcript and grounding an answer…"):
        result = run(query)

    if result["escalated"]:
        reason = (result.get("reason") or "").split("(")[0]
        title, msg = ESCALATION_COPY.get(reason, ("Referred to a human TA",
                                                  "I couldn't confidently answer this, so it's been routed to a TA."))
        st.warning(f"**🙋 {title}**\n\n{msg}", icon="🙋")
        st.caption(f"escalation gate: `{result.get('reason')}`")
    else:
        st.success(_clean_answer(result["answer"]))

        # author + confidence
        cols = st.columns(3)
        authors = ", ".join(result["citations"]) or "—"
        cols[0].metric("Speaker", authors)
        if result.get("rerank_score") is not None:
            cols[1].metric("Relevance", f"{result['rerank_score']*100:.0f}%")
        if result.get("claim_support_ratio") is not None:
            cols[2].metric("Faithfulness", f"{result['claim_support_ratio']*100:.0f}%")
        st.caption(f"answered in {result['loop_count']} retrieval loop(s)")

    # sources / what was discussed — prefer named speakers over Unknown chat/quiz
    # fragments when we have any, so the panel shows real instructor material.
    sources = result.get("sources") or []
    named = [s for s in sources if s["speaker"] != "Unknown"]
    sources = named or sources
    if sources:
        with st.expander(f"📄 Sources — what was discussed ({len(sources)} excerpts)"):
            for s in sources:
                meta = f"**{s['speaker']}** · session {s['session']} · _{s['topic']}_ · relevance {s['score']*100:.0f}%"
                if s.get("timestamp"):
                    meta += f" · {s['timestamp']}"
                st.markdown(meta)
                st.write(s["text"])
                st.divider()

    # follow-up suggestions (only when we actually answered)
    if not result["escalated"]:
        with st.spinner("Thinking of related questions…"):
            followups = suggest_followups(query, result["answer"])
        if followups:
            st.markdown("**You might also ask:**")
            for fq in followups:
                st.button(fq, key=f"fu_{fq}", on_click=_ask, args=(fq,))
else:
    st.info("Ask a question above, or pick one from the sidebar.")
