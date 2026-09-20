import os

# ============================================================
# FORCE OFFLINE MODE
# ============================================================

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


import faiss
import pickle
import numpy as np

from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

INDEX_PATH = "sovereign-ai/data/faiss.index"

DOCUMENTS_PATH = "sovereign-ai/data/documents.pkl"


# ============================================================
# MODEL
# ============================================================

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


# ============================================================
# RETRIEVER
# ============================================================

class Retriever:

    def __init__(self):

        # ----------------------------------------------------
        # Load FAISS
        # ----------------------------------------------------

        print("Loading FAISS index...")

        self.index = faiss.read_index(
            INDEX_PATH
        )

        print(
            f"Loaded {self.index.ntotal} vectors."
        )


        # ----------------------------------------------------
        # Load documents
        # ----------------------------------------------------

        print(
            "Loading document metadata..."
        )

        with open(
            DOCUMENTS_PATH,
            "rb"
        ) as file:

            self.documents = pickle.load(
                file
            )


        print(
            f"Loaded {len(self.documents)} chunks."
        )


        # ----------------------------------------------------
        # Load LOCAL embedding model
        # ----------------------------------------------------

        print(
            "Loading LOCAL embedding model..."
        )

        self.model = SentenceTransformer(
            EMBEDDING_MODEL,
            local_files_only=True
        )


        print(
            "Local embedding model loaded."
        )


    # ========================================================
    # SEARCH
    # ========================================================

        # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query,
        top_k=3
    ):

        # ----------------------------------------------------
        # Create query embedding
        # ----------------------------------------------------

        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        # ----------------------------------------------------
        # Search more candidates internally
        # ----------------------------------------------------

        search_k = min(
            top_k * 3,
            self.index.ntotal
        )

        scores, indices = self.index.search(
            query_embedding,
            search_k
        )

        # ----------------------------------------------------
        # Select best result from each unique source
        # ----------------------------------------------------

        results = []
        used_sources = set()

        for score, index in zip(
            scores[0],
            indices[0]
        ):

            if index == -1:
                continue

            document = self.documents[index]

            source = document["metadata"]["source"]

            # Prefer one result from each document
            if source in used_sources:
                continue

            results.append({
                "score": float(score),
                "text": document["text"],
                "source": source,
                "page": document["metadata"]["page"]
            })

            used_sources.add(source)

            # Stop when we have enough diverse sources
            if len(results) >= top_k:
                break

        return results