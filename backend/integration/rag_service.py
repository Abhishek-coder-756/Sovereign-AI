import os
import re
import pickle
import faiss
import numpy as np
import ollama

from sentence_transformers import SentenceTransformer

from ai.verification.evidence_checker import EvidenceChecker

from .storage import company_paths


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
MODEL_NAME = "qwen2.5:3b"


class NoIndexError(Exception):
    pass


_CACHE = {}


def invalidate(company):
    _CACHE.pop(company, None)


class CompanyRetriever:

    def __init__(self, company):

        paths = company_paths(company)

        if not paths["faiss"].exists():
            raise NoIndexError(
                "No indexed documents found. "
                "Please upload documents and index them first."
            )

        if not paths["documents_pickle"].exists():
            raise NoIndexError(
                "Document metadata is missing. "
                "Please index the documents again."
            )

        self.index = faiss.read_index(
            str(paths["faiss"])
        )

        with open(
            paths["documents_pickle"],
            "rb"
        ) as file:
            self.documents = pickle.load(file)

        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        self.model = SentenceTransformer(
            EMBEDDING_MODEL,
            local_files_only=True
        )

    def search(self, query, top_k=5):

        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        if self.index.ntotal == 0:
            return []

        search_k = min(
            top_k * 3,
            self.index.ntotal
        )

        scores, indices = self.index.search(
            query_embedding,
            search_k
        )

        results = []

        for score, index in zip(scores[0], indices[0]):

            if index == -1:
                continue

            document = self.documents[index]

            results.append({
                "score": float(score),
                "text": document["text"],
                "source": document["metadata"]["source"],
                "page": document["metadata"]["page"]
            })

            if len(results) >= top_k:
                break

        return results


def _get_retriever(company):

    if company not in _CACHE:
        _CACHE[company] = CompanyRetriever(company)

    return _CACHE[company]


def ask(
    company,
    question,
    top_k=5,
    min_score=0.70
):

    retriever = _get_retriever(company)

    results = retriever.search(
        question,
        top_k=top_k
    )

    results = [
        result
        for result in results
        if result["score"] >= min_score
    ]

    if not results:

        return {
            "answer": (
                "I don't have enough evidence in "
                "the provided documents to answer "
                "this question."
            ),
            "sources": [],
            "verification": {
                "verified": False,
                "status": "NO_EVIDENCE",
                "reason": (
                    "No sufficiently relevant "
                    "evidence was found."
                ),
                "method": "retrieval"
            }
        }

    sources = []

    for i, result in enumerate(results, start=1):

        sources.append({
            "id": i,
            "source": result["source"],
            "page": result["page"],
            "score": result["score"],
            "text": result["text"]
        })

    context_parts = []

    for source in sources:

        context_parts.append(
            f"""
SOURCE {source["id"]}

Document:
{source["source"]}

Page:
{source["page"]}

Content:
{source["text"]}
"""
        )

    context = "\n".join(context_parts)

    prompt = f"""
You are a secure local industrial AI assistant.

Answer ONLY using the evidence below.

Every factual document-derived claim MUST contain a citation.

IMPORTANT CITATION RULE:
- Put the citation on the SAME LINE as the factual claim.
- Do NOT put a colon on one line and the factual answer on the next line.
- Do NOT create an uncited introductory sentence before a cited fact.
- If you introduce a formula, value, rule, threshold, observation, or conclusion from the documents, put the citation at the end of that SAME sentence or line.

Example of CORRECT format:
The voter turnout percentage is calculated as (total votes polled ÷ total electors) × 100. [Source 1]

Example of INCORRECT format:
The voter turnout percentage is calculated as:
(total votes polled ÷ total electors) × 100 [Source 1]

Do not invent sources.

Observed values must be cited to the observation document.

Rules and thresholds must be cited to the document containing
the rule.

If a claim combines observation and rule, cite both.

Do not invent actions or events.

If there is insufficient evidence, say:

I don't have enough evidence in the provided documents to answer
this question.

USER QUESTION:
{question}

EVIDENCE:
{context}

Answer concisely.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response["message"]["content"].strip()

# Join citation-bearing facts split after a colon.
# This prevents the verifier from treating a sentence fragment
# such as "The formula is:" as a separate uncited claim.
    answer = re.sub(r":\s*\n\s*", ": ", answer)

    # Normalize combined citations like [Source 1, Source 2, Source 3]
# into the format expected by EvidenceChecker.
    answer = re.sub(
        r"\[(Source \d+(?:\s*,\s*Source \d+)+)\]",
        lambda m: " ".join(
            f"[{citation.strip()}]"
            for citation in m.group(1).split(",")
        ),
        answer
    )

    checker = EvidenceChecker()

    if answer.strip() == "I don't have enough evidence in the provided documents to answer this question.":
        verification = {
            "verified": True,
            "status": "NO_EVIDENCE",
            "reason": "The model refused to answer because the retrieved evidence was insufficient.",
            "method": "insufficient_evidence_refusal"
    }
    else:
        verification = checker.verify(answer, sources, context)


    if not verification["verified"]:

        final_answer = (
            "I could not verify the generated "
            "answer against the provided evidence."
        )

    else:

        final_answer = answer

    return {
        "answer": final_answer,
        "sources": sources,
        "verification": verification
    }
