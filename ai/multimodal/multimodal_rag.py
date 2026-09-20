import sys
from pathlib import Path
import json
import pickle
import time

import ollama
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


# =========================================================
# PATH SETUP
# =========================================================

AI_DIR = Path(__file__).resolve().parents[1]

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))


# =========================================================
# LOCAL IMPORTS
# =========================================================

from verification.evidence_checker import EvidenceChecker


# =========================================================
# MODELS / SETTINGS
# =========================================================

VISION_MODEL = "llava:7b"
TEXT_MODEL = "qwen2.5:3b"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

DEFAULT_TOP_K = 3

MIN_SCORE = 0.70


# =========================================================
# IMAGE ANALYSIS
# =========================================================

def analyze_image(image_path, question):
    """
    Analyze an uploaded image using the local LLaVA model.

    This function is used by the multimodal RAG pipeline.

    Flow:

        Image
          ↓
        LLaVA 7B
          ↓
        Structured JSON observation
    """

    image_path = Path(image_path).resolve()

    print("\n========================================")
    print("IMAGE ANALYSIS")
    print("========================================")

    print("Image path:")
    print(image_path)

    print("Image exists:")
    print(image_path.exists())

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    # =====================================================
    # CALL LOCAL VISION MODEL
    # =====================================================

    response = ollama.chat(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": question,
                "images": [str(image_path)]
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 220,
            "num_ctx": 2048
        },
        keep_alive="30m"
    )

    content = response["message"]["content"].strip()

    print("\nRaw vision response:")
    print(content)

    # =====================================================
    # REMOVE MARKDOWN CODE FENCES
    # =====================================================

    if content.startswith("```"):

        lines = content.splitlines()

        # Remove first ``` or ```json
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        # Remove final ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    # =====================================================
    # TRY DIRECT JSON PARSING
    # =====================================================

    try:

        result = json.loads(content)

        print("\nVision JSON successfully parsed.")

        return result

    except json.JSONDecodeError:

        print(
            "\nWarning: Vision model did not return valid JSON."
        )

    # =====================================================
    # TRY TO EXTRACT JSON FROM EXTRA TEXT
    # =====================================================

    try:

        start = content.find("{")
        end = content.rfind("}")

        if start != -1 and end != -1 and end > start:

            extracted_json = content[
                start:end + 1
            ]

            result = json.loads(
                extracted_json
            )

            print(
                "\nJSON extracted successfully "
                "from vision response."
            )

            return result

    except Exception as error:

        print(
            "JSON extraction failed:",
            error
        )

    # =====================================================
    # SAFE FALLBACK
    # =====================================================

    print(
        "\nUsing safe empty vision observation."
    )

    return {
        "image_type": "",
        "visible_objects": [],
        "visible_equipment": [],
        "visible_components": [],
        "visible_text": [],
        "visible_conditions": [],
        "visible_damage": [],
        "abnormalities": [],
        "confidence": 0.0
    }


# =========================================================
# IMAGE OBSERVATION HELPER
# =========================================================

def analyze_image_only(image_path):
    """
    Analyze an image and return structured visual observations.

    This function is useful when another module needs only
    image understanding without document retrieval.
    """

    return analyze_image(
        image_path,
        """
Analyze the uploaded image and return ONLY valid JSON.

Use exactly this structure:

{
  "image_type": "",
  "visible_objects": [],
  "visible_equipment": [],
  "visible_components": [],
  "visible_text": [],
  "visible_conditions": [],
  "visible_damage": [],
  "abnormalities": [],
  "confidence": 0.0
}

Rules:

1. Identify the image type:
   photograph, technical diagram, engineering drawing,
   document, or screenshot.

2. Identify the main equipment visible in the image.

3. Identify visible components.

4. Read visible labels and text exactly when possible.

5. Report physical conditions only when they are actually
   visible.

6. Do NOT invent:
   corrosion, cracks, leakage, overheating,
   vibration, temperature, pressure, wear,
   mechanical failure, or sensor readings.

7. A technical diagram represents equipment but does not
   prove that the equipment is damaged.

8. If no physical damage is visible:
   "visible_damage": []

9. If no abnormality is visible:
   "abnormalities": []

10. Do not put ordinary equipment names, component names,
    labels, or dates into visible_damage or abnormalities.

11. Confidence must be a number between 0 and 1.

12. Return JSON only.
"""
    )


# =========================================================
# DOCUMENT RETRIEVAL
# =========================================================

def retrieve_documents(
    question,
    top_k=DEFAULT_TOP_K
):
    """
    Retrieve relevant chunks from the local MRPL FAISS index.

    Flow:

        User question
             ↓
        BGE embedding
             ↓
        FAISS search
             ↓
        Relevant document chunks
    """

    print("\n========================================")
    print("DOCUMENT RETRIEVAL")
    print("========================================")

    print(
        "\nSearching local MRPL documents..."
    )

    # =====================================================
    # MRPL STORAGE PATH
    # =====================================================

    storage_root = (
        Path(__file__).resolve().parents[2]
        / "storage"
        / "MRPL"
    )

    index_path = (
        storage_root
        / "index"
        / "faiss.index"
    )

    documents_path = (
        storage_root
        / "index"
        / "documents.pkl"
    )

    print(
        "FAISS index:",
        index_path
    )

    print(
        "Documents:",
        documents_path
    )

    # =====================================================
    # CHECK INDEX
    # =====================================================

    if not index_path.exists():

        raise FileNotFoundError(
            f"MRPL FAISS index not found: {index_path}"
        )

    if not documents_path.exists():

        raise FileNotFoundError(
            f"MRPL document metadata not found: "
            f"{documents_path}"
        )

    # =====================================================
    # LOAD FAISS INDEX
    # =====================================================

    print(
        "\nLoading FAISS index..."
    )

    index = faiss.read_index(
        str(index_path)
    )

    print(
        "FAISS vectors:",
        index.ntotal
    )

    # =====================================================
    # EMPTY INDEX CHECK
    # =====================================================

    if index.ntotal == 0:

        print(
            "FAISS index is empty."
        )

        return []

    # =====================================================
    # LOAD DOCUMENT CHUNKS
    # =====================================================

    print(
        "\nLoading document metadata..."
    )

    with open(
        documents_path,
        "rb"
    ) as file:

        documents = pickle.load(file)

    print(
        "Document chunks loaded:",
        len(documents)
    )

    # =====================================================
    # LOAD LOCAL EMBEDDING MODEL
    # =====================================================

    print(
        "\nLoading local embedding model..."
    )

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL,
        local_files_only=True
    )

    # =====================================================
    # EMBED USER QUESTION
    # =====================================================

    print(
        "\nCreating query embedding..."
    )

    query_embedding = embedding_model.encode(
        [question],
        normalize_embeddings=True
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )

    # =====================================================
    # SEARCH MORE THAN TOP_K
    # =====================================================

    search_k = min(
        max(top_k * 5, 15),
        index.ntotal
    )

    print(
        "\nSearching top",
        search_k,
        "chunks..."
    )

    scores, indices = index.search(
        query_embedding,
        search_k
    )

    # =====================================================
    # COLLECT CANDIDATES
    # =====================================================

    candidates = []

    for score, index_position in zip(
        scores[0],
        indices[0]
    ):

        if index_position == -1:
            continue

        score = float(score)

        # -------------------------------------------------
        # Ignore weak matches
        # -------------------------------------------------

        if score < MIN_SCORE:
            continue

        # -------------------------------------------------
        # Safety check
        # -------------------------------------------------

        if index_position >= len(documents):
            continue

        document = documents[index_position]

        metadata = document.get(
            "metadata",
            {}
        )

        candidates.append({
            "score": score,
            "text": document.get(
                "text",
                ""
            ),
            "source": metadata.get(
                "source",
                "Unknown"
            ),
            "page": metadata.get(
                "page",
                "Unknown"
            )
        })

    # =====================================================
    # NO RELEVANT DOCUMENTS
    # =====================================================

    if not candidates:

        print(
            "\nNo document chunks passed "
            f"similarity threshold {MIN_SCORE}."
        )

        return []

    # =====================================================
    # KEEP BEST CHUNK FROM EACH SOURCE
    # =====================================================

    results = []

    sources_added = set()

    for candidate in candidates:

        source = candidate["source"]

        if source in sources_added:
            continue

        results.append(candidate)

        sources_added.add(source)

    # =====================================================
    # ADD ADDITIONAL CHUNKS
    # =====================================================

    target_count = min(
        top_k + 2,
        len(candidates)
    )

    for candidate in candidates:

        if len(results) >= target_count:
            break

        already_added = False

        for result in results:

            if (
                candidate["source"] == result["source"]
                and candidate["text"] == result["text"]
            ):

                already_added = True

                break

        if already_added:
            continue

        results.append(candidate)

    # =====================================================
    # SORT BY SCORE
    # =====================================================

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # =====================================================
    # DEBUG OUTPUT
    # =====================================================

    print(
        "\nRetrieved evidence chunks:"
    )

    print(
        "========================================"
    )

    for i, result in enumerate(
        results,
        start=1
    ):

        print(
            f"[Source {i}] "
            f"{result['source']} | "
            f"Page {result['page']} | "
            f"Score {result['score']:.4f}"
        )

        print(
            "CONTENT:"
        )

        print(
            result["text"]
        )

        print(
            "----------------------------------------"
        )

    return results


# =========================================================
# FINAL ANSWER GENERATION
# =========================================================

def generate_answer(
    question,
    image_observation,
    retrieved_documents
):
    """
    Generate the final multimodal answer.

    Flow:

        Image observation
              +
        Retrieved documents
              ↓
        Qwen2.5 3B
              ↓
        Evidence-grounded answer
    """

    # =====================================================
    # BUILD DOCUMENT CONTEXT
    # =====================================================

    context_parts = []

    for i, result in enumerate(
        retrieved_documents,
        start=1
    ):

        print(
            "\n========================================"
        )

        print(
            f"SOURCE {i}"
        )

        print(
            "========================================"
        )

        print(
            "DOCUMENT:",
            result["source"]
        )

        print(
            "PAGE:",
            result["page"]
        )

        print(
            "SCORE:",
            result["score"]
        )

        print(
            "\nCONTENT:"
        )

        print(
            result["text"]
        )

        print(
            "----------------------------------------"
        )

        context_parts.append(
            f"""
============================================================
SOURCE {i}
============================================================

SOURCE NUMBER: {i}

DOCUMENT NAME: {result["source"]}

PAGE NUMBER: {result["page"]}

SIMILARITY SCORE: {result["score"]:.4f}

DOCUMENT CONTENT:

{result["text"]}

============================================================
"""
        )

    # =====================================================
    # JOIN DOCUMENT CONTEXT
    # =====================================================

    if context_parts:

        document_context = "\n".join(
            context_parts
        )

    else:

        document_context = (
            "NO DOCUMENT EVIDENCE WAS RETRIEVED."
        )

    # =====================================================
    # BUILD FINAL PROMPT
    # =====================================================

    prompt = f"""
You are a local industrial AI assistant operating in a
confidential on-premise environment.

Your task is to answer the user's question using ONLY:

1. IMAGE OBSERVATION
2. DOCUMENT EVIDENCE

Do NOT use outside knowledge.

Do NOT guess.

Do NOT invent facts.

============================================================
USER QUESTION
============================================================

{question}

============================================================
IMAGE OBSERVATION
============================================================

{json.dumps(
    image_observation,
    indent=2,
    ensure_ascii=False
)}

============================================================
DOCUMENT EVIDENCE
============================================================

{document_context}

============================================================
SOURCE IDENTIFICATION
============================================================

The source numbers shown in DOCUMENT EVIDENCE are the ONLY
valid citation identifiers.

Use exactly:

[Source 1]
[Source 2]
[Source 3]
[Source 4]
[Source 5]

A citation MUST refer to the source whose document content
actually supports the claim.

NEVER change the source numbering.

NEVER cite a source just because it is related to the topic.

============================================================
CORE EVIDENCE RULE
============================================================

Use ONLY information explicitly present in:

IMAGE OBSERVATION

or

DOCUMENT EVIDENCE.

If information is not available, say:

"Insufficient evidence."

Do NOT use general engineering knowledge to fill missing
information.

============================================================
IMAGE EVIDENCE RULES
============================================================

Information directly visible in the image belongs to
IMAGE OBSERVATION.

Only describe objects, components, labels, or conditions
actually provided by the image observation.

Do NOT invent:

- measurements
- temperatures
- vibration values
- operating conditions
- inspection results
- maintenance history
- sensor readings

Document measurements MUST NEVER be described as if they
came from the image.

Correct:

"The image shows a gas turbine with visible compressor
and turbine sections."

Incorrect:

"The image shows vibration of 8.2 mm/s."

============================================================
DOCUMENT EVIDENCE RULES
============================================================

Information obtained from documents MUST have an inline
citation.

Example:

"The Inspection Report records observed vibration of
8.2 mm/s. [Source 2]"

Every document-derived factual statement must have a citation.

If a statement uses information from two sources, cite both.

Example:

"The recorded vibration of 8.2 mm/s exceeds the 7 mm/s
inspection threshold. [Source 2][Source 1]"

============================================================
MEASUREMENT VS THRESHOLD
============================================================

Always distinguish an observed measurement from a limit.

Example:

Observed vibration:
8.2 mm/s [Source 2]

Inspection threshold:
7 mm/s [Source 1]

Conclusion:
8.2 mm/s exceeds the 7 mm/s inspection threshold.
[Source 2][Source 1]

Do NOT confuse measurements with thresholds.

============================================================
TEMPERATURE
============================================================

If the evidence explicitly provides an observed temperature
and a critical threshold, compare them.

Example:

Observed temperature:
587°C [Source 2]

Critical temperature threshold:
580°C [Source 4]

Conclusion:
587°C exceeds the 580°C critical temperature threshold.
[Source 2][Source 4]

Do NOT invent temperatures.

Do NOT invent thresholds.

============================================================
MAINTENANCE PROCEDURES
============================================================

Report ONLY maintenance procedures explicitly present in
the documents.

Each procedure must be a separate claim.

Example:

"Inspect the bearing system. [Source 1]"

"Inspect the rotor assembly. [Source 1]"

Do NOT add procedures from general knowledge.

============================================================
SAFETY REQUIREMENTS
============================================================

Report ONLY safety requirements explicitly present in
the documents.

Every document-derived safety statement requires a citation.

Do NOT add safety recommendations that are not present in
the evidence.

============================================================
EVIDENCE COMPARISON
============================================================

You MAY compare two values only when BOTH values are
explicitly present in the provided evidence.

For example:

8.2 mm/s is present in the Inspection Report. [Source 2]

7 mm/s is present in the Safety SOP. [Source 1]

Therefore:

8.2 mm/s exceeds the 7 mm/s inspection threshold.
[Source 2][Source 1]

Do not perform comparisons using assumed values.

============================================================
FACTS THAT CANNOT BE ESTABLISHED FROM IMAGE
============================================================

The image alone cannot establish:

- vibration measurements
- temperature measurements
- inspection history
- maintenance history
- operating parameters
- sensor readings

Do not attribute these facts to the image.

============================================================
REQUIRED ANSWER STRUCTURE
============================================================

Return exactly these six sections.

### 1. EQUIPMENT AND COMPONENTS

Describe only what is visibly shown in the image.

### 2. RELEVANT MAINTENANCE PROCEDURES

List only maintenance procedures supported by document
evidence.

Cite every document-derived statement.

### 3. VIBRATION LIMITS AND INSPECTION REQUIREMENTS

Include when supported by evidence:

1. observed vibration
2. documented threshold
3. explicit comparison
4. explicit classification
5. required action

Every document-derived statement requires citations.

If either the measurement or threshold is missing:

"Insufficient evidence."

### 4. TEMPERATURE LIMITS AND REQUIREMENTS

Include when supported by evidence:

1. observed temperature
2. documented critical threshold
3. explicit comparison
4. explicit classification
5. required action

Every document-derived statement requires citations.

For temperature:

If observed temperature is above the documented critical
threshold, explicitly state:

"The observed temperature is above the critical threshold
and the condition is CRITICAL."

If the evidence places the temperature in a warning range,
explicitly state:

"The observed temperature is in the WARNING range."

Never leave the numerical comparison implicit.

### 5. SAFETY REQUIREMENTS

List only explicitly documented safety requirements.

Use citations.

### 6. FACTS THAT CANNOT BE ESTABLISHED FROM THE IMAGE

List information that cannot be determined from the image
alone.

============================================================
CITATION FORMAT
============================================================

Use ONLY:

[Source 1]

[Source 2]

[Source 3]

[Source 4]

[Source 5]

Do NOT use:

[Source1]

(Source 1)

Source 1

[1]

============================================================
NO INVENTION RULE
============================================================

NEVER invent or assume:

- measurements
- thresholds
- temperatures
- vibration values
- maintenance procedures
- safety procedures
- inspection results
- equipment conditions
- operating conditions
- sensor readings
- maintenance history

If evidence is missing, write:

"Insufficient evidence."

============================================================
ATOMIC CLAIM RULES
============================================================

1. Each factual or procedural statement must contain only
   one main claim.

2. Do not combine multiple procedures into one sentence.

3. If a source contains multiple actions, write each action
   as a separate sentence.

4. Put a citation on every document-derived sentence.

5. Keep observed measurements separate from thresholds.

6. Keep thresholds separate from required actions.

7. Do not combine condition, action, and notification into
   one claim.

GOOD:

"If turbine temperature exceeds 580°C, treat the condition
as critical. [Source 4]"

"Initiate a controlled shutdown using the approved shutdown
procedure. [Source 4]"

"Notify the maintenance supervisor. [Source 4]"

GOOD:

"If vibration exceeds 7 mm/s, stop normal operation.
[Source 1]"

"Initiate an inspection. [Source 1]"

"Inspect the bearing system. [Source 1]"

BAD:

"If vibration exceeds 7 mm/s, stop normal operation and
initiate an inspection of the bearing and rotor assembly.
[Source 1]"

============================================================
FINAL VERIFICATION
============================================================

Before answering, check:

1. Exactly six sections are present.

2. Image observations are separated from document evidence.

3. Document measurements are not attributed to the image.

4. Every document-derived factual statement has a citation.

5. Every citation points to the correct source.

6. Do not invent information.

7. Do not add uncited recommendations.

8. Do not create a Sources or References section.

9. Do not explain your reasoning process.

10. Do not add meta-explanations.

11. If evidence is missing, say "Insufficient evidence."

Return ONLY the final six-section industrial analysis.
"""

    # =====================================================
    # CALL LOCAL TEXT MODEL
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "GENERATING FINAL ANSWER"
    )

    print(
        "========================================"
    )

    response = ollama.chat(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 900,
            "num_ctx": 4096
        },
        keep_alive="30m"
    )

    answer = response[
        "message"
    ][
        "content"
    ].strip()

    # =====================================================
    # NORMALIZE CITATIONS
    # =====================================================

    replacements = {
        "[Source1]": "[Source 1]",
        "[Source2]": "[Source 2]",
        "[Source3]": "[Source 3]",
        "[Source4]": "[Source 4]",
        "[Source5]": "[Source 5]"
    }

    for old, new in replacements.items():

        answer = answer.replace(
            old,
            new
        )

    return answer


# =========================================================
# DOCUMENT CLAIM EXTRACTION
# =========================================================

def prepare_verification_answer(answer):
    """
    Extract only document-based claims from the final answer.

    Image-only claims are intentionally excluded.
    """

    lines = answer.splitlines()

    document_claims = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # -------------------------------------------------
        # Ignore markdown headings
        # -------------------------------------------------

        if line.startswith("#"):
            continue

        # -------------------------------------------------
        # Ignore standalone citations
        # -------------------------------------------------

        if (
            line.startswith("[Source ")
            and line.endswith("]")
        ):
            continue

        # -------------------------------------------------
        # Ignore explicit no-evidence markers
        # -------------------------------------------------

        if "[No Document Evidence]" in line:
            continue

        # -------------------------------------------------
        # Keep only lines containing citations
        # -------------------------------------------------

        if "[Source " in line:

            document_claims.append(
                line
            )

    # =====================================================
    # NO DOCUMENT CLAIMS
    # =====================================================

    if not document_claims:

        return "NO_DOCUMENT_CLAIMS"

    return "\n".join(
        document_claims
    )


# =========================================================
# FULL MULTIMODAL RAG
# =========================================================

def analyze_with_documents(
    company,
    image_path,
    question,
    top_k=DEFAULT_TOP_K
):
    """
    Complete multimodal RAG pipeline.

    Flow:

        Image
          ↓
        LLaVA 7B
          ↓
        Company document retrieval
          ↓
        Qwen2.5 3B
          ↓
        Evidence Checker
          ↓
        Final result
    """

    start_time = time.time()

    # =====================================================
    # 1. IMAGE ANALYSIS
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "STEP 1: IMAGE ANALYSIS"
    )

    print(
        "========================================"
    )

    image_observation = analyze_image_only(
        image_path
    )

    # =====================================================
    # 2. DOCUMENT RETRIEVAL
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "STEP 2: DOCUMENT RETRIEVAL"
    )

    print(
        "========================================"
    )

    # -----------------------------------------------------
    # IMPORTANT
    #
    # Company-specific retrieval belongs to
    # backend/integration/multimodal_service.py.
    #
    # Therefore this function uses the local MRPL retriever
    # when called directly.
    # -----------------------------------------------------

    documents = retrieve_documents(
        question,
        top_k=top_k
    )

    # =====================================================
    # 3. FINAL ANSWER
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "STEP 3: FINAL ANSWER"
    )

    print(
        "========================================"
    )

    answer = generate_answer(
        question,
        image_observation,
        documents
    )

    # =====================================================
    # 4. BUILD SOURCES
    # =====================================================

    sources = []

    for i, document in enumerate(
        documents,
        start=1
    ):

        sources.append({
            "id": i,
            "source": document["source"],
            "page": document["page"],
            "score": document["score"],
            "text": document["text"]
        })

    # =====================================================
    # 5. PREPARE VERIFICATION CLAIMS
    # =====================================================

    verification_answer = (
        prepare_verification_answer(
            answer
        )
    )

    # =====================================================
    # 6. EVIDENCE VERIFICATION
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "STEP 4: EVIDENCE VERIFICATION"
    )

    print(
        "========================================"
    )

    if (
        verification_answer
        == "NO_DOCUMENT_CLAIMS"
    ):

        verification = {
            "verified": True,
            "status": "NO_DOCUMENT_CLAIMS",
            "reason": (
                "The answer contains no document-derived "
                "claims requiring verification."
            ),
            "method": "document_claim_filter"
        }

    elif not sources:

        verification = {
            "verified": False,
            "status": "NO_EVIDENCE",
            "reason": (
                "No documents were available "
                "for verification."
            ),
            "method": "retrieval"
        }

    else:

        checker = EvidenceChecker()

        evidence = "\n".join(
            document["text"]
            for document in documents
        )

        verification = checker.verify(
            verification_answer,
            sources,
            evidence
        )

    # =====================================================
    # EXECUTION TIME
    # =====================================================

    execution_time = round(
        time.time() - start_time,
        3
    )

    # =====================================================
    # RETURN RESULT
    # =====================================================

    return {
        "answer": answer,
        "image_observation": image_observation,
        "sources": sources,
        "verification": verification,
        "timings": {
            "total": execution_time
        }
    }


# =========================================================
# MAIN TEST
# =========================================================

if __name__ == "__main__":

    print(
        "\n========================================"
    )

    print(
        "MULTIMODAL RAG TEST"
    )

    print(
        "========================================"
    )

    # =====================================================
    # TEST IMAGE
    # =====================================================

    image_path = Path("test.jpeg")

    # =====================================================
    # USER QUESTION
    # =====================================================

    question = """
Analyze the uploaded engineering drawing together with the
available maintenance documents.

Determine:

1. What equipment and components are visibly shown in the image.

2. What maintenance procedures in the documents are relevant
   to a gas turbine.

3. What vibration limits and inspection requirements are stated
   in the documents.

4. What temperature limits are stated in the documents.

5. What safety requirements are stated in the documents.

6. Which facts cannot be established from the image.

Clearly separate image observations from document evidence.

Do not assume that measurements or conditions from an inspection
report belong to the equipment shown in the image unless the
documents explicitly establish that connection.
"""

    # =====================================================
    # CHECK IMAGE
    # =====================================================

    if not image_path.exists():

        print(
            "\nERROR:"
        )

        print(
            f"Test image not found: {image_path}"
        )

        print(
            "\nPlace test.jpeg in the project directory "
            "or change image_path."
        )

        sys.exit(1)

    # =====================================================
    # 1. IMAGE ANALYSIS
    # =====================================================

    image_observation = analyze_image(
        image_path,
        """
Analyze the uploaded image and return ONLY valid JSON.

Use exactly this structure:

{
  "image_type": "",
  "visible_objects": [],
  "visible_equipment": [],
  "visible_components": [],
  "visible_text": [],
  "visible_conditions": [],
  "visible_damage": [],
  "abnormalities": [],
  "confidence": 0.0
}

Rules:

1. Identify the image type.

2. Identify the main equipment shown.

3. Identify visible components.

4. Read visible labels exactly when possible.

5. Report physical conditions only when visible.

6. Do not invent corrosion, cracks, leakage,
   overheating, vibration, temperature, pressure,
   wear, or mechanical failure.

7. A clean technical diagram does not prove damage.

8. If no damage is visible:
   "visible_damage": []

9. If no abnormality is visible:
   "abnormalities": []

10. Confidence must be between 0 and 1.

11. Return JSON only.
"""
    )

    print(
        "\n========================================"
    )

    print(
        "IMAGE OBSERVATION"
    )

    print(
        "========================================"
    )

    print(
        json.dumps(
            image_observation,
            indent=2,
            ensure_ascii=False
        )
    )

    # =====================================================
    # 2. DOCUMENT RETRIEVAL
    # =====================================================

    documents = retrieve_documents(
        question,
        top_k=DEFAULT_TOP_K
    )

    print(
        "\n========================================"
    )

    print(
        "RELEVANT DOCUMENTS"
    )

    print(
        "========================================"
    )

    if not documents:

        print(
            "No documents passed the relevance threshold."
        )

    else:

        for i, result in enumerate(
            documents,
            start=1
        ):

            print(
                f"[Source {i}] "
                f"{result['source']} | "
                f"Page {result['page']} | "
                f"Score {result['score']:.4f}"
            )

    # =====================================================
    # 3. FINAL ANSWER
    # =====================================================

    answer = generate_answer(
        question,
        image_observation,
        documents
    )

    # =====================================================
    # 4. PREPARE SOURCES
    # =====================================================

    verification_sources = []

    for i, document in enumerate(
        documents,
        start=1
    ):

        verification_sources.append({
            "id": i,
            "source": document["source"],
            "page": document["page"],
            "score": document["score"],
            "text": document["text"]
        })

    # =====================================================
    # 5. BUILD EVIDENCE
    # =====================================================

    evidence = "\n".join(
        document["text"]
        for document in documents
    )

    # =====================================================
    # 6. EXTRACT DOCUMENT CLAIMS
    # =====================================================

    verification_answer = (
        prepare_verification_answer(
            answer
        )
    )

    print(
        "\n========================================"
    )

    print(
        "DOCUMENT CLAIMS FOR VERIFICATION"
    )

    print(
        "========================================"
    )

    print(
        verification_answer
    )

    # =====================================================
    # 7. VERIFY
    # =====================================================

    if (
        verification_answer
        == "NO_DOCUMENT_CLAIMS"
    ):

        verification_result = {
            "verified": True,
            "status": "NO_DOCUMENT_CLAIMS",
            "method": "document_claim_filter",
            "reason": (
                "Answer contains no document-based "
                "claims requiring citation verification."
            )
        }

    elif not verification_sources:

        verification_result = {
            "verified": False,
            "status": "NO_EVIDENCE",
            "method": "retrieval",
            "reason": (
                "No document evidence was retrieved."
            )
        }

    else:

        checker = EvidenceChecker()

        verification_result = checker.verify(
            verification_answer,
            verification_sources,
            evidence
        )

        print(
            "\n========================================"
        )

        print(
            "DETAILED VERIFICATION DEBUG"
        )

        print(
            "========================================"
        )

        print(
            json.dumps(
                verification_result,
                indent=2,
                default=str
            )
        )

    # =====================================================
    # 8. VERIFICATION RESULT
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "EVIDENCE VERIFICATION"
    )

    print(
        "========================================"
    )

    print(
        "Verified:",
        verification_result.get(
            "verified"
        )
    )

    print(
        "Status:",
        verification_result.get(
            "status"
        )
    )

    print(
        "Method:",
        verification_result.get(
            "method"
        )
    )

    print(
        "Reason:",
        verification_result.get(
            "reason"
        )
    )

    # =====================================================
    # 9. FINAL ANSWER
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "MULTIMODAL RAG ANSWER"
    )

    print(
        "========================================"
    )

    print(
        answer
    )

    # =====================================================
    # COMPLETE
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "TEST COMPLETE"
    )

    print(
        "========================================"
    )