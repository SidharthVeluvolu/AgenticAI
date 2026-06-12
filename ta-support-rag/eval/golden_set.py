"""The 20 golden queries. Full corpus-grounded reference answers (cited to
speaker) are in golden_keys_4-20.md.
Buckets: 1-17 grounded (answer); 18-19 logistics (escalate); 20 out-of-scope."""

GOLDEN = [
    (1,  "What's the difference between RAG and fine-tuning?", "answer"),
    (2,  "What is hybrid search and why is it mandatory for production?", "answer"),
    (3,  "How does BM25 differ from dense vector search?", "answer"),
    (4,  "What does a re-ranker do in the retrieval pipeline?", "answer"),
    (5,  "What is reciprocal rank fusion?", "answer"),
    (6,  "What is the lost in the middle problem?", "answer"),
    (7,  "What does context rot mean?", "answer"),
    (8,  "What does the faithfulness metric measure?", "answer"),
    (9,  "What does NDCG measure in retrieval evaluation?", "answer"),
    (10, "How do you reduce hallucination in a RAG answer?", "answer"),
    (11, "What is an embedding?", "answer"),
    (12, "What is a vector database and why do you need one?", "answer"),
    (13, "What does temperature control in an LLM?", "answer"),
    (14, "What are the four trade-offs when picking a model?", "answer"),
    (15, "What is the difference between agentic RAG and graph RAG?", "answer"),
    (16, "What are the three chunking strategies covered?", "answer"),
    (17, "How does metadata filtering improve retrieval?", "answer"),
    (18, "Which projects are mandatory for the Gen Academy certification?", "escalate"),
    (19, "When are office hours held?", "escalate"),
    (20, "Can you review my personal AWS bill and tell me how to lower it?", "escalate"),
]
