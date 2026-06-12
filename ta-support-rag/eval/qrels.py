"""Graded-relevance labels (qrels) for the grounded golden queries (1-17).

Anchored on the transcript spans verified during the golden-keys review. A chunk's
grade is the HIGHEST tier whose rule it satisfies:
    2 = directly answers the question
    1 = related / same concept, but not a direct answer
    0 = irrelevant
A rule is a substring (case-insensitive) OR a list of substrings that must ALL be
present in the chunk (an AND rule, for specificity). Queries 18-20 are the escalate
bucket (empty relevant set) — scored by escalation precision, not NDCG.

These are heuristic labels for a baseline NDCG signal, not hand-graded qrels.
Tighten them as the eval loop reveals false positives/negatives.
"""

QRELS = {
    1:  {2: [["fine-tun", "retriev"], ["fine-tun", "borrow"]],
         1: [["fine-tun", "pre-train"], "fine-tuning"]},
    2:  {2: [["hybrid", "production"], ["hybrid", "mandatory"]],
         1: ["hybrid search", "hybrid ranking", "dense and sparse"]},
    3:  {2: [["bm25", "keyword"], ["bm25", "exact"], ["bm25", "dense"]],
         1: [["bm25", "sparse"], "bm25"]},
    4:  {2: ["netflix", ["re-rank", "relevan"], ["reranker", "relevan"]],
         1: ["re-ranker", "reranker"]},
    5:  {2: ["reciprocal rank fusion", ["ensemble retriever", "fus"]],
         1: [["ensemble retriever", "combine"], "rank fusion"]},
    6:  {2: ["lost in the middle", ["middle", "attention"]],
         1: [["context window", "middle"]]},
    7:  {2: ["context rot", ["too much context", "degrad"], ["more context", "degrad"]],
         1: [["context window", "degrad"]]},
    8:  {2: [["faithful", "generation"], ["faithful", "retriev"]],
         1: ["faithful"]},
    9:  {2: ["higher ranks", ["ndcg", "relevan"], ["ndcg", "mrr"]],
         1: ["ndcg", "mrr"]},
    10: {2: [["hallucin", "retriev"], ["hallucin", "enough information"],
             ["hallucin", "don't have"]],
         1: ["hallucin"]},
    11: {2: [["embedding", "numerical"], ["embedding", "number"], ["embedding", "vector"]],
         1: ["embedding model", "what is an embedding"]},
    12: {2: [["vector database", "scale"], ["vector database", "locally"],
             ["vector db", "scale"]],
         1: [["vector database", "pinecone"], "vector database"]},
    13: {2: [["temperature", "random"], ["temperature", "creativ"]],
         1: ["temperature"]},
    14: {2: ["four main trade-off", ["capability", "privacy"], ["privacy", "latency"]],
         1: [["trade-off", "capability"], ["trade-off", "latency"]]},
    15: {2: [["agentic rag", "autonom"], ["graph rag", "node"], ["graph", "relationship"]],
         1: ["agentic rag", "graph rag"]},
    16: {2: ["semantic chunk", "hierarchical chunk", ["fixed", "chunk", "overlap"]],
         1: [["chunk", "strateg"], "chunking"]},
    17: {2: [["metadata", "filter", "subset"], ["metadata filter", "relevan"]],
         1: ["metadata filter"]},
}


def _match(text: str, rule) -> bool:
    if isinstance(rule, (list, tuple)):
        return all(s in text for s in rule)
    return rule in text


def grade(text: str, qid: int) -> int:
    """Relevance grade in {0,1,2} of a chunk's text for golden query `qid`."""
    t = text.lower()
    rules = QRELS.get(qid, {})
    for g in (2, 1):
        for rule in rules.get(g, []):
            if _match(t, rule):
                return g
    return 0
