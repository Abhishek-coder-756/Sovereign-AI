import sys
import re
from pathlib import Path

import ollama


# ============================================================
# ADD AI DIRECTORY TO PYTHON PATH
# ============================================================

AI_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(AI_DIR)
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from rag.retriever import Retriever
from verification.evidence_checker import EvidenceChecker


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "qwen2.5:3b"

DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.70


# ============================================================
# CITATION NORMALIZER
# ============================================================

def normalize_citations(answer):

    # --------------------------------------------------------
    # (Source 1) -> [Source 1]
    # --------------------------------------------------------

    answer = re.sub(
        r"\(Source\s+(\d+)\)",
        r"[Source \1]",
        answer,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # (Source 1 and Source 2)
    # --------------------------------------------------------

    answer = re.sub(
        r"\(Source\s+(\d+)\s+and\s+Source\s+(\d+)\)",
        r"[Source \1][Source \2]",
        answer,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # (Source 1, Source 2)
    # --------------------------------------------------------

    def replace_multiple_parentheses(match):

        numbers = re.findall(
            r"\d+",
            match.group(0)
        )

        return "".join(
            f"[Source {number}]"
            for number in numbers
        )

    answer = re.sub(
        r"\(Source\s+\d+(?:\s*,\s*Source\s+\d+)+\)",
        replace_multiple_parentheses,
        answer,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # Source 1 -> [Source 1]
    # --------------------------------------------------------

    answer = re.sub(
        r"(?<![\[\w])Source\s+(\d+)(?![\]\w])",
        r"[Source \1]",
        answer,
        flags=re.IGNORECASE
    )

    return answer

# ============================================================
# CLEAN ANSWER
# ============================================================

def clean_answer(answer):

    # Remove code fences

    answer = re.sub(
        r"```(?:text|markdown)?",
        "",
        answer,
        flags=re.IGNORECASE
    )

    answer = answer.replace(
        "```",
        ""
    )

    # Remove Sources / References section

    answer = re.split(
        r"\n\s*(?:sources?|references?)\s*:\s*\n",
        answer,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    return answer.strip()


# ============================================================
# RAG PIPELINE
# ============================================================

class RAGPipeline:

    def __init__(self):

        print("Initializing RAG system...")

        self.retriever = Retriever()

        self.evidence_checker = EvidenceChecker()

        print("RAG system ready.")

    # ========================================================
    # ASK
    # ========================================================

    def ask(
        self,
        question,
        top_k=DEFAULT_TOP_K,
        min_score=DEFAULT_MIN_SCORE
    ):

        # ====================================================
        # STEP 1 — RETRIEVAL
        # ====================================================

        print("\nSearching documents...")

        results = self.retriever.search(
            question,
            top_k=top_k
        )

        # ====================================================
        # STEP 2 — SCORE FILTER
        # ====================================================

        results = [
            result
            for result in results
            if result["score"] >= min_score
        ]

        # ====================================================
        # STEP 3 — NO EVIDENCE
        # ====================================================

        if not results:

            return {

                "answer": (
                    "I don't have enough evidence in "
                    "the provided documents to answer "
                    "this question."
                ),

                "sources": [],

                "evidence_map": [],

                "verification": {

                    "verified": False,

                    "status": "NO_EVIDENCE",

                    "reason": (
                        "No sufficiently relevant "
                        "evidence was found."
                    ),

                    "citations": [],

                    "verification_method": "retrieval"
                }
            }

        # ====================================================
        # STEP 4 — CREATE SOURCE LIST
        # ====================================================

        sources = []

        for i, result in enumerate(
            results,
            start=1
        ):

            sources.append({

                "id": i,

                "source": result["source"],

                "page": result["page"],

                "score": result["score"],

                "text": result["text"]
            })

        # ====================================================
        # STEP 5 — BUILD EVIDENCE CONTEXT
        # ====================================================

        context_parts = []

        for source in sources:

            context_parts.append(
                f"""
============================================================
SOURCE {source['id']}
============================================================

Document:
{source['source']}

Page:
{source['page']}

Similarity Score:
{source['score']:.4f}

Content:
{source['text']}
"""
            )

        context = "\n".join(
            context_parts
        )

        # ====================================================
        # STEP 6 — PROMPT
        # ====================================================

        prompt = f"""
You are a secure industrial AI assistant.

Answer the user question using ONLY the evidence
provided below.

Do not use outside knowledge.

============================================================
CITATION RULES
============================================================

Every factual claim MUST have a citation.

Use ONLY:

[Source 1]
[Source 2]
[Source 3]

Never invent source numbers.

If a claim contains an observed value AND a rule,
cite both sources.

Example:

Observed temperature was 587°C. [Source 1]

Temperatures above 580°C are classified as critical.
[Source 2]

Therefore, the temperature is critical because 587°C
exceeds the 580°C threshold. [Source 1][Source 2]

============================================================
VIBRATION RULE
============================================================

Observed vibration:

8.2 mm/s

Maintenance threshold:

Above 7 mm/s requires inspection.

Therefore:

8.2 mm/s > 7 mm/s

The result is:

INSPECTION REQUIRED

Never classify 8.2 mm/s as monitoring.

============================================================
TEMPERATURE RULE
============================================================

Observed temperature:

587°C

Critical threshold:

Above 580°C

Therefore:

587°C > 580°C

The result is:

CRITICAL

Never classify 587°C as normal or warning.

============================================================
ACTION RULE
============================================================

Do not claim that an action happened unless the evidence
explicitly says it happened.

If evidence says:

"controlled shutdown is recommended"

you may say:

"Controlled shutdown is recommended."

Do NOT say:

"Controlled shutdown was initiated."

============================================================
INSUFFICIENT EVIDENCE
============================================================

If the evidence does not contain enough information,
respond exactly:

I don't have enough evidence in the provided documents
to answer this question.

============================================================
USER QUESTION
============================================================

{question}

============================================================
EVIDENCE
============================================================

{context}

============================================================
FINAL REQUIREMENTS
============================================================

Before answering:

1. Identify every factual claim.

2. Find the source supporting that claim.

3. Observations must cite observation sources.

4. Rules must cite rule sources.

5. Combined observation + rule claims must cite both.

6. Verify numerical comparisons.

7. Never classify 8.2 mm/s as monitoring.

8. Never classify 587°C as normal or warning.

9. Do not invent actions.

10. Every factual statement must have a citation.

============================================================
OUTPUT
============================================================

Write concise factual statements.

Example:

GT-01 has an observed temperature of 587°C. [Source 1]

The Maintenance Manual classifies temperatures above
580°C as critical. [Source 2]

GT-01 has an observed vibration of 8.2 mm/s. [Source 1]

The Maintenance Manual states that vibration above
7 mm/s requires inspection. [Source 2]

Therefore, GT-01 is in a critical condition due to the
observed temperature and vibration exceeding their
respective thresholds. [Source 1][Source 2]

============================================================
FINAL ANSWER
============================================================
"""

        # ====================================================
        # STEP 7 — LOCAL QWEN
        # ====================================================

        print(
            "Generating answer with local Qwen..."
        )

        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        answer = (
            response["message"]["content"]
            .strip()
        )

        # ====================================================
        # STEP 8 — CLEAN
        # ====================================================

        answer = clean_answer(
            answer
        )

        print(
            "\n========================================"
        )

        print(
            "RAW QWEN ANSWER"
        )

        print(
            "========================================"
        )

        print(answer)

        # ====================================================
        # STEP 9 — NORMALIZE CITATIONS
        # ====================================================

        answer = normalize_citations(
            answer
        )

        print(
            "\n========================================"
        )

        print(
            "NORMALIZED ANSWER"
        )

        print(
            "========================================"
        )

        print(answer)

        # ====================================================
        # STEP 10 — VERIFY
        # ====================================================

        print(
            "\nVerifying generated answer..."
        )

        verification = (
            self.evidence_checker.verify(
                answer,
                sources,
                context
            )
        )

        # ====================================================
        # STEP 11 — EVIDENCE MAP
        # ====================================================

        evidence_map = verification.get(
            "evidence_map",
            []
        )

        # ====================================================
        # STEP 12 — REJECT FAILED ANSWERS
        # ====================================================

        if not verification["verified"]:

            return {

                "answer": (
                    "I could not verify the generated "
                    "answer against the provided evidence."
                ),

                "sources": sources,

                "evidence_map": evidence_map,

                "verification": verification
            }

        # ====================================================
        # STEP 13 — VERIFIED ANSWER
        # ====================================================

        return {

            "answer": answer,

            "sources": sources,

            "evidence_map": evidence_map,

            "verification": verification
        }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("\n")

    print(
        "========================================"
    )

    print(
        "       SOVEREIGN AI RAG TEST"
    )

    print(
        "========================================"
    )

    rag = RAGPipeline()

    question = (
        "What is the condition of gas turbine GT-01 "
        "based on its temperature and vibration?"
    )

    result = rag.ask(
        question,
        top_k=5,
        min_score=0.70
    )

    # ========================================================
    # ANSWER
    # ========================================================

    print("\n")

    print(
        "========================================"
    )

    print(
        "RAG ANSWER"
    )

    print(
        "========================================"
    )

    print(
        result["answer"]
    )

    # ========================================================
    # SOURCES
    # ========================================================

    print("\n")

    print(
        "========================================"
    )

    print(
        "SOURCES"
    )

    print(
        "========================================"
    )

    if not result["sources"]:

        print(
            "No sufficiently relevant evidence found."
        )

    else:

        for source in result["sources"]:

            print(
                f"[Source {source['id']}] "
                f"{source['source']} "
                f"| Page {source['page']} "
                f"| Score {source['score']:.4f}"
            )

    # ========================================================
    # EVIDENCE MAP
    # ========================================================

    print("\n")

    print(
        "========================================"
    )

    print(
        "EVIDENCE MAP"
    )

    print(
        "========================================"
    )

    if not result["evidence_map"]:

        print(
            "No evidence mapping available."
        )

    else:

        for item in result["evidence_map"]:

            print(
                "\n----------------------------------------"
            )

            print(
                "Claim:",
                item["claim"]
            )

            print(
                "Status:",
                item["status"]
            )

            print(
                "Citations:",
                item["citations"]
            )

            for evidence_item in item["evidence"]:

                print(
                    f"  -> [Source "
                    f"{evidence_item.get('source_id')}] "
                    f"{evidence_item.get('document', '')} "
                    f"| Page "
                    f"{evidence_item.get('page', '')} "
                    f"| Score "
                    f"{evidence_item.get('score', 0):.4f} "
                    f"| Status: "
                    f"{evidence_item.get('status')}"
                )

    # ========================================================
    # VERIFICATION
    # ========================================================

    print("\n")

    print(
        "========================================"
    )

    print(
        "EVIDENCE VERIFICATION"
    )

    print(
        "========================================"
    )

    verification = result["verification"]

    print(
        "Verified:",
        verification["verified"]
    )

    print(
        "Status:",
        verification["status"]
    )

    print(
        "Reason:",
        verification["reason"]
    )

    if "method" in verification:

        print(
            "Method:",
            verification["method"]
        )

    if "verification_method" in verification:

        print(
            "Method:",
            verification["verification_method"]
        )

    # ========================================================
    # COMPLETE
    # ========================================================

    print("\n")

    print(
        "========================================"
    )

    print(
        "TEST COMPLETE"
    )

    print(
        "========================================"
    )