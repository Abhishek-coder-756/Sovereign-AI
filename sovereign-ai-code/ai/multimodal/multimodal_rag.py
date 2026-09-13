import sys
from pathlib import Path
import json
import ollama


# =========================================================
# PATH SETUP
# =========================================================

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from rag.retriever import Retriever
from verification.evidence_checker import EvidenceChecker


# =========================================================
# MODELS / SETTINGS
# =========================================================

VISION_MODEL = "qwen2.5vl:3b"
TEXT_MODEL = "qwen2.5:3b"

MODEL_NAME = VISION_MODEL

DEFAULT_TOP_K = 3
MIN_SCORE = 0.70


# =========================================================
# IMAGE ANALYSIS
# =========================================================

def analyze_image(image_path, question):

    image_path = Path(image_path).resolve()

    print("Image path:")
    print(image_path)

    print("Image exists:", image_path.exists())

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": question,
                "images": [str(image_path)],
            }
        ],
    )

    content = response["message"]["content"].strip()


    # -----------------------------------------------------
    # Remove markdown code fences if model adds them
    # -----------------------------------------------------

    if content.startswith("```"):

        content = content.replace(
            "```json",
            "",
            1
        )

        content = content.replace(
            "```",
            "",
            1
        )

        content = content.strip()


    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    try:

        return json.loads(content)

    except json.JSONDecodeError:

        print(
            "Warning: Vision model did not return valid JSON."
        )

        print("Raw vision response:")
        print(content)


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
# DOCUMENT RETRIEVAL
# =========================================================

def retrieve_documents(
    question,
    top_k=DEFAULT_TOP_K
):
    print("\nSearching local MRPL documents...")

    storage_root = (
        Path(__file__).resolve().parents[2]
        / "storage"
        / "MRPL"
    )

    index_path = storage_root / "index" / "faiss.index"
    documents_path = storage_root / "index" / "documents.pkl"

    # ============================================================
    # CHECK INDEX FILES
    # ============================================================

    if not index_path.exists():
        raise FileNotFoundError(
            f"MRPL FAISS index not found: {index_path}"
        )

    if not documents_path.exists():
        raise FileNotFoundError(
            f"MRPL document metadata not found: {documents_path}"
        )

    # ============================================================
    # IMPORT LOCAL RAG COMPONENTS
    # ============================================================

    import pickle
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    # ============================================================
    # LOAD FAISS INDEX
    # ============================================================

    print("Loading MRPL FAISS index...")

    index = faiss.read_index(
        str(index_path)
    )

    # ============================================================
    # LOAD DOCUMENT CHUNKS
    # ============================================================

    with open(
        documents_path,
        "rb"
    ) as file:
        documents = pickle.load(file)

    # ============================================================
    # LOAD LOCAL EMBEDDING MODEL
    # ============================================================

    embedding_model = SentenceTransformer(
        "BAAI/bge-small-en-v1.5",
        local_files_only=True
    )

    # ============================================================
    # EMBED USER QUESTION
    # ============================================================

    query_embedding = embedding_model.encode(
        [question],
        normalize_embeddings=True
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )

    # ============================================================
    # CHECK EMPTY INDEX
    # ============================================================

    if index.ntotal == 0:
        return []

    # ============================================================
    # RETRIEVE MORE CHUNKS
    #
    # We retrieve more than top_k because one document may have
    # several useful chunks.
    # ============================================================

    search_k = min(
        max(top_k * 5, 15),
        index.ntotal
    )

    scores, indices = index.search(
        query_embedding,
        search_k
    )

    # ============================================================
    # COLLECT RELEVANT CANDIDATES
    # ============================================================

    candidates = []

    for score, index_position in zip(
        scores[0],
        indices[0]
    ):

        if index_position == -1:
            continue

        score = float(score)

        # Ignore weak matches
        if score < MIN_SCORE:
            continue

        document = documents[index_position]

        candidates.append({
            "score": score,
            "text": document["text"],
            "source": document["metadata"]["source"],
            "page": document["metadata"]["page"]
        })

    # ============================================================
    # FIRST: KEEP BEST CHUNK FROM EACH DOCUMENT
    #
    # This ensures that Safety SOP, Inspection Report and
    # Maintenance Manual can all appear in the evidence.
    # ============================================================

    results = []

    sources_added = set()

    for candidate in candidates:

        source = candidate["source"]

        if source in sources_added:
            continue

        results.append(candidate)

        sources_added.add(source)

    # ============================================================
    # SECOND: ADD ADDITIONAL CHUNKS
    #
    # This is important because Maintenance_Manual.pdf has
    # multiple chunks and the temperature/vibration information
    # may be in a different chunk.
    # ============================================================

    for candidate in candidates:

        if len(results) >= top_k + 2:
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

    # ============================================================
    # SORT BY SIMILARITY SCORE
    # ============================================================

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # ============================================================
    # DEBUG OUTPUT
    # ============================================================

    print("\nRetrieved evidence chunks:")
    print("========================================")

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

        print("CONTENT:")
        print(result["text"])

        print("----------------------------------------")

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
    Generate the final multimodal answer using:
    1. Image observations from Qwen2.5-VL
    2. Retrieved MRPL document evidence
    3. Local Qwen2.5:3b text model
    """

    # ============================================================
    # BUILD DOCUMENT CONTEXT
    # ============================================================

    context_parts = []

    for i, result in enumerate(
        retrieved_documents,
        start=1
    ):

        # --------------------------------------------------------
        # DEBUG: PRINT ACTUAL RETRIEVED DOCUMENT CONTENT
        # --------------------------------------------------------

        print("\n========================================")
        print(f"SOURCE {i}")
        print("========================================")

        print("DOCUMENT:", result["source"])
        print("PAGE:", result["page"])
        print("SCORE:", result["score"])

        print("\nCONTENT:")
        print(result["text"])

        print("----------------------------------------")

        # --------------------------------------------------------
        # ADD DOCUMENT TO LLM CONTEXT
        # --------------------------------------------------------

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

    # ============================================================
    # JOIN ALL DOCUMENT CONTEXT
    # ============================================================

    document_context = "\n".join(context_parts)

    # ============================================================
    # BUILD FINAL PROMPT
    # ============================================================

    prompt = f"""
You are a local industrial AI assistant operating in a
confidential on-premise environment.

Your task is to analyze the user's question using ONLY:

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

{json.dumps(image_observation, indent=2)}

============================================================
DOCUMENT EVIDENCE
============================================================

{document_context}

============================================================
SOURCE IDENTIFICATION
============================================================

The source numbers shown in DOCUMENT EVIDENCE are the ONLY
valid citation identifiers.

For example:

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

Use ONLY information explicitly present in the IMAGE
OBSERVATION or DOCUMENT EVIDENCE.

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

For example:

Correct:
"The image shows a gas turbine with compressor,
combustion chamber, turbine section, shaft and exhaust."

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

If a statement uses information from two different sources,
cite both sources.

Example:

"The recorded vibration of 8.2 mm/s exceeds the 7 mm/s
inspection threshold. [Source 2][Source 1]"

============================================================
IMPORTANT: MEASUREMENT VS THRESHOLD
============================================================

Always distinguish an observed measurement from a limit
or threshold.

For example:

Observed vibration:
8.2 mm/s [Source 2]

Inspection threshold:
7 mm/s [Source 1]

Conclusion:
8.2 mm/s exceeds the 7 mm/s inspection threshold.
[Source 2][Source 1]

Similarly:

Observed temperature:
587°C [Source 2]

Critical temperature threshold:
580°C [Source 4]

Conclusion:
587°C exceeds the 580°C critical temperature threshold.
[Source 2][Source 4]

Do NOT confuse measurements with thresholds.

============================================================
MAINTENANCE PROCEDURES
============================================================

Report only maintenance procedures explicitly present in
the documents.

For example, if the evidence states:

"Inspect the bearing system and rotor assembly."

you may write:

"Inspect the bearing system and rotor assembly. [Source 1]"

Do NOT add procedures from general knowledge.

============================================================
SAFETY REQUIREMENTS
============================================================

Report only safety requirements explicitly present in the
documents.

For example:

"Only authorized maintenance personnel may inspect internal
turbine components. [Source 1]"

"If turbine temperature exceeds 580°C, treat the condition
as critical and initiate a controlled shutdown. [Source 4]"

"If vibration exceeds 7 mm/s, stop normal operation and
initiate an inspection. [Source 1]"

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

Do not perform comparisons using assumed or missing values.

============================================================
FACTS THAT CANNOT BE ESTABLISHED FROM THE IMAGE
============================================================

Clearly distinguish what the image cannot establish.

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

Return exactly these six sections:

### 1. EQUIPMENT AND COMPONENTS

Describe only what is visibly shown in the image.

### 2. RELEVANT MAINTENANCE PROCEDURES

List only maintenance procedures supported by document
evidence, with citations.

### 3. VIBRATION LIMITS AND INSPECTION REQUIREMENTS

Include:
1. observed vibration
2. documented threshold
3. explicit comparison
4. explicit classification
5. required action
6. citations for every document-derived claim

### 4. TEMPERATURE LIMITS AND REQUIREMENTS

Include:
1. observed temperature
2. documented critical threshold
3. explicit comparison
4. explicit classification
5. required action
6. citations for every document-derived claim

For numerical conditions, ALWAYS explicitly state the resulting classification.

For temperature:
- If observed temperature > critical threshold, explicitly state:
  "The observed temperature is above the critical threshold and the condition is CRITICAL."
- If observed temperature is within the warning range, explicitly state that it is in the WARNING range.
- Never leave the numerical comparison as an implicit conclusion.

For vibration:
- If observed vibration > 7 mm/s, explicitly state:
  "The observed vibration exceeds the inspection threshold and INSPECTION IS REQUIRED."
- Never leave the inspection conclusion implicit.

Every numerical conclusion must include the relevant [Source N] citations.

### 5. SAFETY REQUIREMENTS

List only explicitly documented safety requirements.

Use citations.

### 6. FACTS THAT CANNOT BE ESTABLISHED FROM THE IMAGE

List information that cannot be determined from the image
alone.

============================================================
CITATION FORMAT
============================================================

Use ONLY this format:

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

Use the exact format:

[Source 1]

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
FINAL VERIFICATION BEFORE ANSWERING
============================================================

Before producing the final answer, check all of the following:

1. Did I answer all six required sections?

2. Did I separate image observations from document evidence?

3. Did I avoid attributing document measurements to the image?

4. Did I cite every document-derived factual statement?

5. Does every citation point to the source that actually
   contains the claim?

6. Did I correctly identify 8.2 mm/s as the observed vibration
   from the Inspection Report?

7. Did I correctly identify 7 mm/s as the vibration threshold
   from the Safety SOP?

8. Did I correctly identify 587°C as the observed temperature
   from the Inspection Report?

9. Did I correctly identify 580°C as the critical temperature
   threshold from the Safety SOP?

10. Did I avoid inventing information?

11. Did I avoid adding uncited recommendations?

12. Did I avoid writing a separate Sources or References
    section?

13. Did I avoid writing meta-explanations such as:
    "You may compare these values because..."
    or
    "Both values are explicitly present..."

Return ONLY the final six-section industrial analysis.

ATOMIC CLAIM RULES:

1. Each factual or procedural statement must contain only one main claim.
2. Do not combine multiple procedures into one sentence.
3. If a source contains multiple actions, write each action as a separate sentence.
4. Put a citation on every document-derived sentence.
5. Keep observed measurements separate from thresholds.
6. Keep thresholds separate from required actions.
7. Do not combine condition + action + notification into one claim.

GOOD:
"If turbine temperature exceeds 580°C, treat the condition as critical. [Source 4]"
"Initiate a controlled shutdown using the approved shutdown procedure. [Source 4]"
"Notify the maintenance supervisor and control-room operator. [Source 4]"

BAD:
"If turbine temperature exceeds 580°C, treat the condition as critical, initiate shutdown, and notify the supervisor. [Source 4]"

GOOD:
"If vibration exceeds 7 mm/s, stop normal operation. [Source 1]"
"Initiate an inspection. [Source 1]"
"Inspect the bearing system and rotor assembly. [Source 1]"

BAD:
"If vibration exceeds 7 mm/s, stop normal operation and initiate an inspection of the bearing and rotor assembly. [Source 1]"
"""

    # ============================================================
    # CALL LOCAL TEXT MODEL
    # ============================================================

    response = ollama.chat(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response["message"]["content"].strip()

    # ============================================================
    # NORMALIZE CITATION FORMATTING
    # ============================================================

    answer = answer.replace(
        "[Source1]",
        "[Source 1]"
    )

    answer = answer.replace(
        "[Source2]",
        "[Source 2]"
    )

    answer = answer.replace(
        "[Source3]",
        "[Source 3]"
    )

    return answer



# =========================================================
# DOCUMENT CLAIM EXTRACTION FOR VERIFICATION
# =========================================================

def prepare_verification_answer(answer):

    lines = answer.splitlines()

    document_claims = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Ignore headings
        if line.startswith("==="):
            continue

        # Ignore standalone citations such as:
        # [Source 1]
        # [Source 2]
        # [Source 3]
        if (
            line.startswith("[Source ")
            and line.endswith("]")
        ):
            continue

        # Ignore statements that explicitly have no document evidence
        if "[No Document Evidence]" in line:
            continue

        # -------------------------------------------------
        # Keep only claims that contain an inline citation
        # -------------------------------------------------

        if "[Source " in line:
            document_claims.append(line)

    # -----------------------------------------------------
    # No document claims
    # -----------------------------------------------------

    if not document_claims:
        return "NO_DOCUMENT_CLAIMS"

    return "\n".join(document_claims)


# =========================================================
# MULTIMODAL RAG
# =========================================================

def analyze_with_documents(
    company,
    image_path,
    question,
    top_k=3
):
    """
    Full multimodal pipeline:

    Image
        ↓
    Qwen2.5-VL
        ↓
    Company-scoped document retrieval
        ↓
    Qwen2.5
        ↓
    Evidence verification
    """

    import time

    start_time = time.time()

    # -----------------------------------------------------
    # 1. Analyze image
    # -----------------------------------------------------

    image_observation = analyze_image_only(
        image_path
    )

    # -----------------------------------------------------
    # 2. Retrieve company documents
    # -----------------------------------------------------

    documents = _retrieve_company_documents(
        company,
        question,
        top_k=top_k
    )

    # -----------------------------------------------------
    # 3. Generate answer
    # -----------------------------------------------------

    answer = generate_answer(
        question,
        image_observation,
        documents
    )

    # -----------------------------------------------------
    # 4. Build sources
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 5. Prepare claims for verification
    # -----------------------------------------------------

    verification_answer = prepare_verification_answer(
        answer
    )

    # -----------------------------------------------------
    # 6. Verify evidence
    # -----------------------------------------------------

    if verification_answer == "NO_DOCUMENT_CLAIMS":

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
                "No company documents were available "
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

    execution_time = round(
        time.time() - start_time,
        3
    )

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
# IMAGE-ONLY QUESTION
# =========================================================

def answer_image_question(
    image_path,
    question
):
    """
    Answer simple visual questions directly from the image.

    No RAG.
    No company documents.
    No evidence verification.
    """

    prompt = f"""
You are a local industrial visual AI assistant.

Answer ONLY the user's question using information
visible in the uploaded image.

USER QUESTION:
{question}

RULES:

1. Answer directly and concisely.
2. Use only what is visible in the image.
3. Do not use company documents.
4. Do not use external knowledge.
5. Do not invent measurements or conditions.
6. Do not discuss maintenance procedures unless the user asks.
7. Do not discuss temperature or vibration unless visible
   in the image.
8. If the image does not contain enough information,
   say "Insufficient visual evidence."

Return ONLY the answer.
"""

    with open(
        image_path,
        "rb"
    ) as file:
        image_bytes = file.read()

    response = ollama.chat(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [image_bytes]
            }
        ]
    )

    return response["message"]["content"].strip()

# =========================================================
# QUESTION ROUTER
# =========================================================

def is_image_only_question(question):

    q = question.lower().strip()

    image_only_patterns = [
        "what is it",
        "what is this",
        "what is shown",
        "what does this show",
        "identify this",
        "identify the equipment",
        "what equipment is this",
        "what equipment is shown",
        "describe this image",
        "describe the image",
        "what can you see",
        "what do you see",
        "which equipment is shown",
        "which equipment is this"
    ]

    return any(
        pattern in q
        for pattern in image_only_patterns
    )


# =========================================================
# ANSWER IMAGE-ONLY QUESTION
# =========================================================

def answer_image_question(image_path, question):
    """
    Answer the user's question using ONLY the uploaded image.

    No RAG.
    No company documents.
    No document evidence.
    No evidence verification.
    """

    image_observation = analyze_image_only(image_path)

    prompt = f"""
You are a local industrial vision AI assistant.

Answer the user's question using ONLY the uploaded image.

USER QUESTION:
{question}

IMAGE OBSERVATION:
{json.dumps(image_observation, indent=2)}

RULES:

1. Answer ONLY what the user asked.
2. Use only information visible in the image observation.
3. Do not use maintenance documents.
4. Do not use external knowledge.
5. Do not invent measurements.
6. Do not invent temperature.
7. Do not invent vibration.
8. Do not invent damage.
9. Do not discuss maintenance procedures unless the user asks.
10. Do not discuss safety requirements unless the user asks.
11. Do not create unnecessary sections.
12. Do not add citations.
13. Do not add an evidence verification section.
14. Keep the answer concise.

If the image does not contain enough information to answer,
say:

"Insufficient visual evidence."

Return only the answer to the user's question.
"""

    response = ollama.chat(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"].strip()
# =========================================================
# MAIN TEST
# =========================================================

if __name__ == "__main__":

    image_path = "test.jpeg"


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
    # 1. VISION
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

1. Identify the image type:
   photograph, technical diagram, engineering drawing,
   document, or screenshot.

2. Identify the main equipment shown in the image.
   Use the visible shape, structure, labels, and arrangement
   of components to identify recognizable industrial equipment.

3. If the image is a recognizable engineering diagram,
   identify the equipment even if its exact equipment name
   is not written as a label.

4. For this type of image, consider equipment such as:
   gas turbine, steam turbine, compressor, pump, motor,
   generator, heat exchanger, valve, or piping system.

5. Identify visible components.
   For a turbine diagram, components may include:
   inlet, compressor stages, combustion chamber,
   turbine/expansion section, shaft, and exhaust.

6. Read visible labels and text exactly when possible.
   Preserve the original text.

7. Report physical conditions only when they are actually
   visible.

8. Do NOT invent:
   corrosion, cracks, leakage, overheating, vibration,
   temperature, pressure, wear, or mechanical failure.

9. A clean technical diagram represents equipment,
   but does NOT indicate that the equipment is damaged.

10. If no physical damage is visible, return:
    "visible_damage": []

11. If no abnormal physical condition is visible, return:
    "abnormalities": []

12. Do not put ordinary equipment names, component names,
    labels, or dates into visible_damage or abnormalities.

13. Confidence must be a number between 0 and 1.

14. Return JSON only.
"""
    )


    print("\n========================================")
    print("IMAGE OBSERVATION")
    print("========================================")

    print(image_observation)


    # =====================================================
    # 2. RAG
    # =====================================================

    documents = retrieve_documents(
        question,
        top_k=DEFAULT_TOP_K
    )


    print("\n========================================")
    print("RELEVANT DOCUMENTS")
    print("========================================")


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
    # 4. EVIDENCE VERIFICATION
    # =====================================================

    checker = EvidenceChecker()


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


    evidence = "\n".join(
        document["text"]
        for document in documents
    )


    # -----------------------------------------------------
    # Only document-based claims are sent to the verifier.
    # Image-only statements are intentionally excluded.
    # -----------------------------------------------------

    verification_answer = prepare_verification_answer(
        answer
    )


    print("\n========================================")
    print("DOCUMENT CLAIMS FOR VERIFICATION")
    print("========================================")

    print(verification_answer)


    # -----------------------------------------------------
    # If there are no document claims, verification is not
    # needed because the answer contains only image/refusal
    # information.
    # -----------------------------------------------------

    if verification_answer == "NO_DOCUMENT_CLAIMS":

        verification_result = {
            "verified": True,
            "status": "NO_DOCUMENT_CLAIMS",
            "method": "document_claim_filter",
            "reason": (
                "Answer contains no document-based claims "
                "requiring citation verification."
            )
        }

    else:

        verification_result = checker.verify(
            verification_answer,
            verification_sources,
            evidence
        )

        print("\n========================================")
        print("DETAILED VERIFICATION DEBUG")
        print("========================================")

        print(json.dumps(
            verification_result,
            indent=2,
            default=str
    ))

    print("========================================")


    # =====================================================
    # 5. VERIFICATION RESULT
    # =====================================================

    print("\n========================================")
    print("EVIDENCE VERIFICATION")
    print("========================================")

    print("Verified:")
    print(verification_result["verified"])

    print("Status:")
    print(verification_result["status"])

    print("Method:")
    print(verification_result["method"])

    print("Reason:")
    print(verification_result["reason"])


    # =====================================================
    # 6. FINAL ANSWER
    # =====================================================

    print("\n========================================")
    print("MULTIMODAL RAG ANSWER")
    print("========================================")

    print(answer)


    # =====================================================
    # COMPLETE
    # =====================================================

    print("\n========================================")
    print("TEST COMPLETE")
    print("========================================")