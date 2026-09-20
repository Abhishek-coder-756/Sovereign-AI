"""
Global Knowledge RAG Service for Sovereign AI — SIH26117.
Manages conversation-scoped public web sources, local BGE embeddings, and isolated FAISS indexes.
Strictly isolated from company private document stores:
    storage/global/<conversation_id>/
Zero external AI APIs: inference and retrieval are completely local.
"""

import json
import os
import pickle
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

import faiss
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.agents.agent import get_embedding_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_STORAGE_ROOT = PROJECT_ROOT / "storage" / "global"
GLOBAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_conv_id(conversation_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", str(conversation_id or "default"))
    return cleaned or "default"


def get_global_paths(conversation_id: str) -> Dict[str, Path]:
    safe_id = _safe_conv_id(conversation_id)
    conv_dir = GLOBAL_STORAGE_ROOT / safe_id
    index_dir = conv_dir / "index"
    sources_dir = conv_dir / "sources"

    for d in (conv_dir, index_dir, sources_dir):
        d.mkdir(parents=True, exist_ok=True)

    return {
        "root": conv_dir,
        "index_dir": index_dir,
        "sources_dir": sources_dir,
        "faiss": index_dir / "faiss.index",
        "documents_pickle": index_dir / "documents.pkl",
        "sources_json": conv_dir / "sources.json",
    }


def _load_sources_meta(paths: Dict[str, Path]) -> List[Dict[str, Any]]:
    if not paths["sources_json"].exists():
        return []
    try:
        with open(paths["sources_json"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_sources_meta(paths: Dict[str, Path], sources: List[Dict[str, Any]]):
    with open(paths["sources_json"], "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2)


def _load_documents_pickle(paths: Dict[str, Path]) -> List[Dict[str, Any]]:
    if not paths["documents_pickle"].exists():
        return []
    try:
        with open(paths["documents_pickle"], "rb") as f:
            return pickle.load(f)
    except Exception:
        return []


def _save_documents_pickle(paths: Dict[str, Path], documents: List[Dict[str, Any]]):
    with open(paths["documents_pickle"], "wb") as f:
        pickle.dump(documents, f)


def index_global_source(
    conversation_id: str,
    url: str,
    title: str,
    text: str,
) -> Dict[str, Any]:
    """
    Chunks text, creates local BGE embeddings, and updates the conversation-isolated FAISS index.
    """
    paths = get_global_paths(conversation_id)
    sources = _load_sources_meta(paths)
    documents = _load_documents_pickle(paths)

    # Determine source_id (1-indexed sequence)
    existing = next((s for s in sources if s.get("url") == url), None)
    if existing:
        source_id = existing["id"]
        # Remove old chunks for this source
        documents = [d for d in documents if d.get("metadata", {}).get("source_id") != source_id]
    else:
        existing_ids = [s["id"] for s in sources if "id" in s]
        source_id = max(existing_ids, default=0) + 1

    # Chunk the text
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    text_chunks = splitter.split_text(text)

    new_documents = []
    for idx, chunk in enumerate(text_chunks, start=1):
        new_documents.append({
            "text": chunk,
            "metadata": {
                "source_id": source_id,
                "source": title,
                "title": title,
                "url": url,
                "page": idx,  # Chunks act as sections/pages
            }
        })

    all_documents = documents + new_documents

    # Rebuild FAISS index with all chunks for this conversation
    embed_model = get_embedding_model()
    all_texts = [d["text"] for d in all_documents]

    if all_texts:
        embeddings = embed_model.encode(
            all_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings = np.asarray(embeddings, dtype="float32")
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        faiss.write_index(index, str(paths["faiss"]))
        _save_documents_pickle(paths, all_documents)

    now_iso = datetime.now(timezone.utc).isoformat()
    source_entry = {
        "id": source_id,
        "source_id": source_id,
        "url": url,
        "title": title,
        "chunks_count": len(new_documents),
        "added_at": now_iso,
        "last_fetched_at": now_iso,
        "status": "FETCHED",
    }

    if existing:
        for idx, s in enumerate(sources):
            if s.get("url") == url:
                sources[idx] = source_entry
                break
    else:
        sources.append(source_entry)

    _save_sources_meta(paths, sources)
    return source_entry


def remove_global_source(conversation_id: str, source_id_or_url: Any) -> bool:
    """
    Removes a global source and its chunks from the conversation index.
    """
    paths = get_global_paths(conversation_id)
    sources = _load_sources_meta(paths)
    documents = _load_documents_pickle(paths)

    target_id = None
    target_url = None

    for s in sources:
        if str(s.get("id")) == str(source_id_or_url) or s.get("url") == str(source_id_or_url):
            target_id = s.get("id")
            target_url = s.get("url")
            break

    if target_id is None and target_url is None:
        return False

    sources = [s for s in sources if s.get("id") != target_id and s.get("url") != target_url]
    documents = [
        d for d in documents
        if d.get("metadata", {}).get("source_id") != target_id
        and d.get("metadata", {}).get("url") != target_url
    ]

    _save_sources_meta(paths, sources)
    _save_documents_pickle(paths, documents)

    # Rebuild or clear FAISS index
    if documents:
        embed_model = get_embedding_model()
        all_texts = [d["text"] for d in documents]
        embeddings = embed_model.encode(all_texts, normalize_embeddings=True, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype="float32")
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        faiss.write_index(index, str(paths["faiss"]))
    else:
        if paths["faiss"].exists():
            paths["faiss"].unlink()

    return True


def get_conversation_sources(conversation_id: str) -> List[Dict[str, Any]]:
    paths = get_global_paths(conversation_id)
    return _load_sources_meta(paths)


def retrieve_global_evidence(
    conversation_id: str,
    query: str,
    top_k: int = 5,
    min_score: float = 0.20,
) -> List[Dict[str, Any]]:
    """
    Retrieves the most relevant chunks from the conversation's private global FAISS index.
    Always ensures lead overview chunks are present for broad/summary questions.
    """
    paths = get_global_paths(conversation_id)
    if not paths["faiss"].exists() or not paths["documents_pickle"].exists():
        return []

    documents = _load_documents_pickle(paths)
    if not documents:
        return []

    try:
        index = faiss.read_index(str(paths["faiss"]))
    except Exception:
        return []

    if index.ntotal == 0:
        return []

    embed_model = get_embedding_model()
    q_emb = embed_model.encode([query], normalize_embeddings=True)
    q_emb = np.asarray(q_emb, dtype="float32")

    search_k = min(top_k * 4, index.ntotal)
    scores, indices = index.search(q_emb, search_k)

    results = []
    seen_texts = set()

    for score, idx in zip(scores[0], indices[0]):
        if idx == -1 or idx >= len(documents):
            continue
        if float(score) < min_score:
            continue

        doc = documents[idx]
        text = doc["text"]
        if text in seen_texts:
            continue
        seen_texts.add(text)

        meta = doc.get("metadata", {})
        results.append({
            "id": len(results) + 1,
            "source": meta.get("title") or meta.get("source") or "Web Source",
            "title": meta.get("title") or meta.get("source") or "Web Source",
            "url": meta.get("url", ""),
            "page": meta.get("page", 1),
            "score": float(score),
            "text": text,
            "source_type": "global_web",
        })

        if len(results) >= top_k:
            break

    # If results are sparse or query is overview-oriented, include lead chunks (Page 1)
    lead_chunks = [d for d in documents if d.get("metadata", {}).get("page") == 1]
    for lead in lead_chunks:
        lead_text = lead["text"]
        if lead_text not in seen_texts:
            meta = lead.get("metadata", {})
            results.insert(0, {
                "id": len(results) + 1,
                "source": meta.get("title") or meta.get("source") or "Web Source",
                "title": meta.get("title") or meta.get("source") or "Web Source",
                "url": meta.get("url", ""),
                "page": 1,
                "score": 0.85,
                "text": lead_text,
                "source_type": "global_web",
            })
            seen_texts.add(lead_text)
            if len(results) > top_k + 1:
                results.pop()

    # Re-number IDs sequentially 1..N
    for i, r in enumerate(results, start=1):
        r["id"] = i

    return results


class GlobalRAGService:
    @staticmethod
    def index_source(conversation_id: str, url: str, title: str, text: str):
        return index_global_source(conversation_id, url, title, text)

    @staticmethod
    def retrieve(conversation_id: str, query: str, top_k: int = 5, min_score: float = 0.28):
        return retrieve_global_evidence(conversation_id, query, top_k, min_score)

    @staticmethod
    def get_sources(conversation_id: str):
        return get_conversation_sources(conversation_id)

    @staticmethod
    def remove_source(conversation_id: str, source_id_or_url: Any):
        return remove_global_source(conversation_id, source_id_or_url)


def get_global_rag_service() -> GlobalRAGService:
    return GlobalRAGService()

