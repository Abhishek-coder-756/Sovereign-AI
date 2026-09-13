from pdf_loader import load_pdf
from chunker import chunk_documents
from vector_store import VectorStore

from sentence_transformers import SentenceTransformer

import numpy as np
import pickle
from pathlib import Path
import faiss


# ==================================================
# Configuration
# ==================================================

DOCUMENTS_DIR = Path(
    "sovereign-ai/data/documents"
)

INDEX_PATH = Path(
    "sovereign-ai/data/faiss.index"
)

DOCUMENTS_PATH = Path(
    "sovereign-ai/data/documents.pkl"
)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


# ==================================================
# Ingest all PDFs
# ==================================================

def ingest_documents():

    print("\n")
    print("========================================")
    print("      INDUSTRIAL DOCUMENT INGESTION")
    print("========================================")


    # ==========================================
    # 1. Find PDF files
    # ==========================================

    pdf_files = sorted(
        DOCUMENTS_DIR.glob("*.pdf")
    )


    if not pdf_files:

        print("\nNo PDF files found.")

        return


    print("\nPDF files found:")

    for pdf_file in pdf_files:

        print(
            " -",
            pdf_file.name
        )


    # ==========================================
    # 2. Load all PDFs
    # ==========================================

    print("\n========================================")
    print("1. LOADING DOCUMENTS")
    print("========================================")


    all_documents = []


    for pdf_file in pdf_files:

        print(
            f"\nLoading: {pdf_file.name}"
        )


        documents = load_pdf(
            pdf_file
        )


        print(
            f"Pages loaded: {len(documents)}"
        )


        all_documents.extend(
            documents
        )


    print(
        f"\nTotal pages loaded: {len(all_documents)}"
    )


    # ==========================================
    # 3. Create chunks
    # ==========================================

    print("\n========================================")
    print("2. CREATING CHUNKS")
    print("========================================")


    chunks = chunk_documents(
        all_documents
    )


    print(
        f"Total chunks created: {len(chunks)}"
    )


    # ==========================================
    # 4. Load embedding model
    # ==========================================

    print("\n========================================")
    print("3. LOADING EMBEDDING MODEL")
    print("========================================")


    print(
        f"Model: {EMBEDDING_MODEL}"
    )


    model = SentenceTransformer(
        EMBEDDING_MODEL
    )


    print(
        "Embedding model loaded."
    )


    # ==========================================
    # 5. Create embeddings
    # ==========================================

    print("\n========================================")
    print("4. CREATING EMBEDDINGS")
    print("========================================")


    texts = [

        chunk["text"]

        for chunk in chunks

    ]


    embeddings = model.encode(

        texts,

        normalize_embeddings=True,

        show_progress_bar=True

    )


    embeddings = np.asarray(

        embeddings,

        dtype="float32"

    )


    print(
        f"\nEmbedding shape: {embeddings.shape}"
    )


    # ==========================================
    # 6. Create FAISS index
    # ==========================================

    print("\n========================================")
    print("5. CREATING FAISS VECTOR STORE")
    print("========================================")


    dimension = embeddings.shape[1]


    vector_store = VectorStore(
        dimension
    )


    vector_store.add_documents(

        embeddings,

        chunks

    )


    print(
        f"Vectors stored: {vector_store.index.ntotal}"
    )


    # ==========================================
    # 7. Save FAISS index
    # ==========================================

    print("\n========================================")
    print("6. SAVING FAISS INDEX")
    print("========================================")


    INDEX_PATH.parent.mkdir(

        parents=True,

        exist_ok=True

    )


    faiss.write_index(

        vector_store.index,

        str(INDEX_PATH)

    )


    print(
        f"Saved: {INDEX_PATH}"
    )


    # ==========================================
    # 8. Save document metadata
    # ==========================================

    print("\n========================================")
    print("7. SAVING DOCUMENT METADATA")
    print("========================================")


    DOCUMENTS_PATH.parent.mkdir(

        parents=True,

        exist_ok=True

    )


    with open(

        DOCUMENTS_PATH,

        "wb"

    ) as file:

        pickle.dump(

            chunks,

            file

        )


    print(
        f"Saved: {DOCUMENTS_PATH}"
    )


    # ==========================================
    # 9. Print document summary
    # ==========================================

    print("\n========================================")
    print("DOCUMENT SUMMARY")
    print("========================================")


    document_counts = {}


    for chunk in chunks:

        source = chunk["metadata"]["source"]

        document_counts[source] = (

            document_counts.get(source, 0) + 1

        )


    for source, count in document_counts.items():

        print(
            f"📄 {source}: {count} chunks"
        )


    # ==========================================
    # Complete
    # ==========================================

    print("\n========================================")
    print("      INGESTION COMPLETE")
    print("========================================")

    print(
        f"Total PDFs: {len(pdf_files)}"
    )

    print(
        f"Total chunks: {len(chunks)}"
    )

    print(
        f"Vector dimension: {dimension}"
    )

    print("========================================\n")


# ==================================================
# Run
# ==================================================

if __name__ == "__main__":

    ingest_documents()