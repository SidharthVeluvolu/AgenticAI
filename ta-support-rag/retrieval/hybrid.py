"""Step 3. Hybrid retrieval: dense + BM25 fused via RRF.

LangChain EnsembleRetriever wraps the dense retriever (Chroma, local) and the BM25
retriever, combining their ranked lists with reciprocal rank fusion at RRF_WEIGHTS.
Runs inside each loop iteration, over the pre-filtered subset.

Free / local stack: dense = Chroma + sentence-transformers (replaces Pinecone).

Pre-filter handling:
  - Chroma takes a native `where` filter (cheap).
  - BM25 has no metadata filter, so we rebuild it over the filtered doc subset
    per call. BM25 build is in-memory over ~3k docs — negligible.
An empty/None filter searches the whole corpus.
"""
from __future__ import annotations

import pickle

from config import settings

# Module-level singletons — load the embeddings, Chroma store and the doc corpus
# once, not per query.
_EMB = None
_DENSE = None
_DOCS = None


def _embeddings():
    global _EMB
    if _EMB is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _EMB = HuggingFaceEmbeddings(model_name=settings.EMBED_MODEL)
    return _EMB


def _dense_store():
    global _DENSE
    if _DENSE is None:
        from langchain_chroma import Chroma
        _DENSE = Chroma(
            collection_name=settings.COLLECTION,
            persist_directory=settings.CHROMA_DIR,
            embedding_function=_embeddings(),
        )
    return _DENSE


def _all_docs():
    global _DOCS
    if _DOCS is None:
        with open(settings.BM25_PATH, "rb") as fh:
            _DOCS = pickle.load(fh)
    return _DOCS


def _chroma_where(metadata_filter: dict | None):
    """Convert {field: value | [values]} to a Chroma `where` clause."""
    if not metadata_filter:
        return None
    clauses = []
    for field, val in metadata_filter.items():
        if isinstance(val, (list, tuple, set)):
            clauses.append({field: {"$in": list(val)}})
        else:
            clauses.append({field: val})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _matches(meta: dict, metadata_filter: dict | None) -> bool:
    if not metadata_filter:
        return True
    for field, val in metadata_filter.items():
        got = meta.get(field)
        if isinstance(val, (list, tuple, set)):
            if got not in val:
                return False
        elif got != val:
            return False
    return True


def get_hybrid_retriever(metadata_filter: dict | None = None):
    """Return an EnsembleRetriever (dense + BM25, RRF) scoped by metadata_filter.

    Returns None if the pre-filter selects an empty subset (caller escalates).
    """
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever

    # dense, with native Chroma filter
    search_kwargs = {"k": settings.TOP_K_RETRIEVE}
    where = _chroma_where(metadata_filter)
    if where is not None:
        search_kwargs["filter"] = where
    dense_retriever = _dense_store().as_retriever(search_kwargs=search_kwargs)

    # sparse, over the filtered subset
    subset = [d for d in _all_docs() if _matches(d.metadata, metadata_filter)]
    if not subset:
        return None
    bm25 = BM25Retriever.from_documents(subset)
    bm25.k = settings.TOP_K_RETRIEVE

    return EnsembleRetriever(
        retrievers=[dense_retriever, bm25],
        weights=settings.RRF_WEIGHTS,
    )


def retrieve(query: str, metadata_filter: dict | None = None):
    """Convenience: hybrid-retrieve candidate docs for a query (pre-rerank)."""
    retriever = get_hybrid_retriever(metadata_filter)
    if retriever is None:
        return []
    return retriever.invoke(query)
