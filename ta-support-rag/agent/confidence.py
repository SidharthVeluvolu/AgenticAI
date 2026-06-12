"""Step 6. The confidence gates. Decides answer vs escalate.

GATES, not a blended score — the gate that fires IS the diagnosis. Escalate if ANY:
  - out_of_scope / empty filter subset
  - rerank_top_score < RERANK_THRESHOLD       (retrieval found nothing relevant)
  - model emitted INSUFFICIENT_CONTEXT
  - reflection == 'no' after retries exhausted (agent isn't confident)
  - claim_support_ratio < CLAIM_THRESHOLD      (answer not grounded in citations)
"""
from config import settings


def should_escalate(rerank_score: float, claim_ratio, out_of_scope: bool,
                    retries_exhausted: bool, reflection: str = "yes",
                    insufficient: bool = False) -> tuple:
    """Return (escalate: bool, reason: str | None). reason names the gate."""
    if out_of_scope:
        return True, "out_of_scope"
    if rerank_score is not None and rerank_score < settings.RERANK_THRESHOLD:
        return True, f"low_rerank_score({rerank_score:.2f}<{settings.RERANK_THRESHOLD})"
    if insufficient:
        return True, "model_insufficient_context"
    if retries_exhausted and reflection == "no":
        return True, "reflection_no_after_retries"
    if claim_ratio is not None and claim_ratio < settings.CLAIM_THRESHOLD:
        return True, f"low_claim_support({claim_ratio:.2f}<{settings.CLAIM_THRESHOLD})"
    return False, None
