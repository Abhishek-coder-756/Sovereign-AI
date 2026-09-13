import os

# ============================================================
# FORCE HUGGING FACE OFFLINE MODE
# ============================================================

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


from sentence_transformers import SentenceTransformer


# ============================================================
# LOCAL MODEL
# ============================================================

MODEL_NAME = "BAAI/bge-small-en-v1.5"


# ============================================================
# EMBEDDING MODEL
# ============================================================

class EmbeddingModel:

    def __init__(self):

        print("Loading LOCAL embedding model...")

        self.model = SentenceTransformer(
            MODEL_NAME,
            local_files_only=True
        )

        print("Local embedding model loaded.")


    # ========================================================
    # SINGLE TEXT
    # ========================================================

    def embed_text(self, text):

        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )

        return embedding


    # ========================================================
    # MULTIPLE DOCUMENTS
    # ========================================================

    def embed_documents(self, documents):

        texts = [
            document["text"]
            for document in documents
        ]

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True
        )

        return embeddings


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("\n")
    print("========================================")
    print("   LOCAL EMBEDDING MODEL TEST")
    print("========================================")

    model = EmbeddingModel()

    embedding = model.embed_text(
        "Gas turbine GT-01 temperature is 587°C."
    )

    print("\nEmbedding dimension:")
    print(len(embedding))

    print("\nFirst 10 values:")
    print(embedding[:10])

    print("\n========================================")
    print("OFFLINE EMBEDDING TEST COMPLETE")
    print("========================================")