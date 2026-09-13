from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from ai.rag.document_loader import load_document, SUPPORTED_DOCUMENT_EXTENSIONS
from ai.rag.chunker import chunk_documents

from .storage import company_paths
from . import documents_registry


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def ingest_company_documents(company):

    paths = company_paths(company)

    doc_files = sorted([
        f for f in paths["documents"].iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS
    ])

    if not doc_files:
        return {
            "indexed": False,
            "documents": 0,
            "chunks": 0,
            "per_file": []
        }

    all_documents = []
    per_file = []

    for doc_file in doc_files:

        try:
            documents = load_document(doc_file)
        except Exception:
            documents = []

        all_documents.extend(documents)

        per_file.append({
            "filename": doc_file.name,
            "pages": len(documents),
            "chunks": 0
        })

    chunks = chunk_documents(
        all_documents
    )

    for item in per_file:

        item["chunks"] = sum(
            1
            for chunk in chunks
            if chunk["metadata"]["source"]
            == item["filename"]
        )

    if not chunks:
        return {
            "indexed": False,
            "documents": len(doc_files),
            "chunks": 0,
            "per_file": per_file
        }

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        local_files_only=True
    )

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32"
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(embeddings)

    faiss.write_index(
        index,
        str(paths["faiss"])
    )

    import pickle

    with open(
        paths["documents_pickle"],
        "wb"
    ) as file:
        pickle.dump(
            chunks,
            file
        )

    for item in per_file:
        if item["chunks"] > 0:
            documents_registry.mark_indexed(
                company,
                item["filename"],
                item["pages"],
                item["chunks"]
            )

    return {
        "indexed": True,
        "documents": len(doc_files),
        "chunks": len(chunks),
        "dimension": dimension,
        "per_file": per_file
    }
