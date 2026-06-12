"""Step 1. Build both indexes from chunks. OFFLINE batch step, runs once.

Free / local stack (no paid API keys):
  Dense  -> Chroma (persisted) with local sentence-transformers embeddings.
  Sparse -> BM25Retriever (pickled to disk).

Same two-index shape the README locks (dense + sparse for hybrid RRF); only the
backends are local. Metadata (session, speaker, topic) rides along so the online
pre-filter and the speaker citation work.

Run: `python -m ingestion.index`  ->  builds .store/chroma + .store/bm25.pkl
Acceptance (README Stage 1): both indexes populate; counts match chunk count.
"""
from __future__ import annotations

import os
import pickle

from config import settings
from ingestion.chunk import load_transcript, chunk_transcript, _default_path


def _to_documents(chunks: list[dict]):
    """chunk dicts -> LangChain Documents (Chroma metadata must be scalar)."""
    from langchain_core.documents import Document
    docs = []
    for c in chunks:
        md = {k: ("" if v is None else v) for k, v in c["metadata"].items()}
        docs.append(Document(page_content=c["content"], metadata=md))
    return docs


def _embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=settings.EMBED_MODEL)


def build_dense_index(chunks: list[dict]):
    """Build/persist the Chroma dense index from chunks. Returns the vector store."""
    from langchain_chroma import Chroma
    os.makedirs(settings.CHROMA_DIR, exist_ok=True)
    docs = _to_documents(chunks)
    store = Chroma.from_documents(
        documents=docs,
        embedding=_embeddings(),
        collection_name=settings.COLLECTION,
        persist_directory=settings.CHROMA_DIR,
    )
    return store


def build_sparse_index(chunks: list[dict]):
    """Build the BM25 retriever over chunks and pickle it. Returns the retriever."""
    from langchain_community.retrievers import BM25Retriever
    docs = _to_documents(chunks)
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = settings.TOP_K_RETRIEVE
    os.makedirs(os.path.dirname(settings.BM25_PATH), exist_ok=True)
    with open(settings.BM25_PATH, "wb") as fh:
        pickle.dump(docs, fh)  # persist the corpus; rebuild retriever on load (cheap)
    return retriever


def build_all():
    text = load_transcript(_default_path())
    chunks = chunk_transcript(text)
    print(f"chunks: {len(chunks)}")
    print(f"building dense index (Chroma, {settings.EMBED_MODEL}) ...")
    dense = build_dense_index(chunks)
    print(f"building sparse index (BM25) ...")
    build_sparse_index(chunks)
    # verify both populated
    dense_count = dense._collection.count()
    with open(settings.BM25_PATH, "rb") as fh:
        sparse_count = len(pickle.load(fh))
    print(f"dense  (Chroma) docs: {dense_count}")
    print(f"sparse (BM25)   docs: {sparse_count}")
    assert dense_count == len(chunks) == sparse_count, "index/chunk count mismatch"
    print("OK — both indexes populated and counts match.")


if __name__ == "__main__":
    build_all()
