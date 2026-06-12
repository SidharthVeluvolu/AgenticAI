"""Step 7. Online metrics: faithfulness, citation accuracy, escalation precision.

Runs the full agentic loop over the 20 golden queries and reports:
  - faithfulness        : mean claim_support_ratio over ANSWERED queries (grounding.py)
  - citation accuracy   : answered grounded queries whose cited speaker matches the
                          golden key's expected speaker(s)
  - escalation precision: of queries the bot escalated, how many SHOULD have
                          (golden behavior == "escalate"; queries 18-20)
  - escalation recall   : of should-escalate queries, how many the bot caught

Run: python -m eval.online_metrics
"""
from __future__ import annotations

# Expected citing speaker(s) per grounded query, from the corrected
# golden_keys_4-20.md (first names; #9 and #15 corrected to Aishwarya).
EXPECTED_SPEAKERS = {
    4: ["Arvind"], 5: ["Arvind"], 6: ["Aishwarya"], 7: ["Aishwarya"],
    8: ["Aishwarya"], 9: ["Aishwarya"], 10: ["Aishwarya", "Arvind"],
    11: ["Aishwarya", "Arvind"], 12: ["Arvind"], 13: ["Aishwarya"],
    14: ["Aishwarya"], 15: ["Aishwarya"], 16: ["Aishwarya"], 17: ["Arvind"],
}


def escalation_precision(results: list, golden: list) -> float:
    """results: [{qid, escalated}]; golden: [(qid, q, behavior)]."""
    behavior = {qid: beh for qid, _, beh in golden}
    escalated = [r for r in results if r["escalated"]]
    if not escalated:
        return 0.0
    correct = sum(1 for r in escalated if behavior.get(r["qid"]) == "escalate")
    return correct / len(escalated)


def _cites_expected(citations: list, expected: list) -> bool:
    cited = " ".join(citations).lower()
    return any(name.lower() in cited for name in expected)


def _run():
    from eval.golden_set import GOLDEN
    from agent.loop import run
    import time

    behavior = {qid: beh for qid, _, beh in GOLDEN}
    results = []
    print(f"{'Q':<4}{'gold':<10}{'got':<10}{'faith':>7}  detail")
    for qid, q, beh in GOLDEN:
        t = time.time()
        r = run(q)
        r["qid"] = qid
        results.append(r)
        got = "escalate" if r["escalated"] else "answer"
        mark = "ok" if got == beh else "MISS"
        faith = "-" if r["claim_support_ratio"] is None else f"{r['claim_support_ratio']:.2f}"
        detail = r["reason"] if r["escalated"] else f"cites={r['citations']}"
        print(f"Q{qid:<3}{beh:<10}{got:<10}{faith:>7}  [{mark}] {str(detail)[:42]}  ({time.time()-t:.1f}s)")

    answered = [r for r in results if not r["escalated"]]
    grounded_answered = [r for r in answered if r["qid"] in EXPECTED_SPEAKERS]

    faithfulness = (sum(r["claim_support_ratio"] for r in answered) / len(answered)
                    if answered else 0.0)
    cite_ok = sum(1 for r in grounded_answered
                  if _cites_expected(r["citations"], EXPECTED_SPEAKERS[r["qid"]]))
    cite_acc = cite_ok / len(grounded_answered) if grounded_answered else 0.0

    should = [qid for qid, _, b in GOLDEN if b == "escalate"]
    caught = sum(1 for r in results if r["escalated"] and behavior[r["qid"]] == "escalate")
    esc_prec = escalation_precision(results, GOLDEN)
    esc_rec = caught / len(should) if should else 0.0

    behavior_acc = sum(1 for r in results
                       if ("escalate" if r["escalated"] else "answer") == behavior[r["qid"]]) / len(results)

    print("\n── resolution metrics (20 golden queries, local llama3.2:3b) ──")
    print(f"  behavior accuracy     : {behavior_acc:.2f}  (answer-vs-escalate correct)")
    print(f"  faithfulness          : {faithfulness:.2f}  (mean claim support, {len(answered)} answered)")
    print(f"  citation accuracy     : {cite_acc:.2f}  ({cite_ok}/{len(grounded_answered)} grounded-answered)")
    print(f"  escalation precision  : {esc_prec:.2f}")
    print(f"  escalation recall     : {esc_rec:.2f}  ({caught}/{len(should)} should-escalate)")


if __name__ == "__main__":
    _run()
