from ai.multimodal.multimodal_rag import (
    analyze_image,
    generate_answer,
    prepare_verification_answer,
)

from ai.verification.evidence_checker import EvidenceChecker

from .storage import company_paths

import faiss
import pickle
import numpy as np
import json
import ollama

from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
MIN_SCORE = 0.70
TEXT_MODEL = "qwen2.5:3b"

def analyze_image_only(image_path):

    prompt = """
Analyze this industrial image.

Return JSON with exactly these fields:

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

Do not invent damage or abnormalities that are not visibly present.
"""

    return analyze_image(image_path, prompt)


def analyze_with_documents(
    company,
    image_path,
    question,
    top_k=3
):

    image_observation = analyze_image_only(
        image_path
    )

    documents = _retrieve_company_documents(
        company,
        question,
        top_k=top_k
    )

    answer = generate_answer(
        question,
        image_observation,
        documents
    )

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

    verification_answer = prepare_verification_answer(
        answer
    )

    if verification_answer == "NO_DOCUMENT_CLAIMS":

        verification = {
            "verified": True,
            "status": "NO_DOCUMENT_CLAIMS",
            "reason": "The answer contains no document-derived claims requiring verification.",
            "method": "evidence_checker"
        }

    elif not sources:

        verification = {
            "verified": False,
            "status": "NO_EVIDENCE",
            "reason": "No company documents were available for verification.",
            "method": "retrieval"
        }

    else:

        evidence = "\n".join(
            document["text"]
            for document in documents
        )

        checker = EvidenceChecker()

        verification = checker.verify(
            verification_answer,
            sources,
            evidence
        )

    return {
        "answer": answer,
        "image_observation": image_observation,
        "sources": sources,
        "verification": verification,
        "timings": {}
    }


# =========================================================
# IMAGE-ONLY QUESTION
# =========================================================

def answer_image_question(
    image_path,
    question
):
    """
    Answer a simple question using ONLY the uploaded image.

    No RAG.
    No company documents.
    No evidence verification.
    """

    image_observation = analyze_image_only(
        image_path
    )

    prompt = f"""
You are a local industrial vision AI assistant.

Answer ONLY the user's question using the uploaded image.

USER QUESTION:
{question}

IMAGE OBSERVATION:
{json.dumps(image_observation, indent=2)}

RULES:

1. Answer only what the user asked.
2. Use only information visible in the image.
3. Do not use maintenance documents.
4. Do not use external knowledge.
5. Do not invent measurements.
6. Do not invent temperature.
7. Do not invent vibration.
8. Do not invent damage.
9. Do not discuss maintenance unless the user asks.
10. Do not discuss safety unless the user asks.
11. Do not create unnecessary sections.
12. Do not add citations.
13. Do not add evidence verification.
14. Keep the answer concise.

If the image does not contain enough information, say:

"Insufficient visual evidence."

Return only the answer.
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
# QUESTION ROUTER
# =========================================================

# =========================================================
# QUESTION ROUTER
# =========================================================

def is_image_only_question(question):

    q = (question or "").strip().lower()

    # -----------------------------------------------------
    # Document / industrial-data questions MUST use RAG
    # -----------------------------------------------------

    document_keywords = [
        "manual",
        "maintenance",
        "sop",
        "inspection report",
        "document",
        "documents",
        "procedure",
        "procedures",
        "limit",
        "limits",
        "threshold",
        "thresholds",
        "according to",
        "report",
        "safety requirement",
        "safety requirements",
        "vibration",
        "temperature",
        "sensor",
        "maintenance history",
    ]

    if any(keyword in q for keyword in document_keywords):
        return False

    # -----------------------------------------------------
    # Simple visual questions
    # -----------------------------------------------------

    image_phrases = [

    # =====================================================
    # GENERAL IMAGE QUESTIONS
    # =====================================================

    "what is this",
    "what is it",
    "what is this image",
    "what is in this image",
    "what is in the image",
    "what does this show",
    "what does the image show",
    "what does this image show",
    "what does this contain",
    "what does the image contain",
    "what does this image contain",
    "what can you see",
    "what do you see",
    "tell me about this image",
    "tell me about the image",
    "describe this",
    "describe this image",
    "describe the image",
    "can you describe this image",
    "can you describe the image",
    "give me a description of this image",
    "give me a description of the image",

    # =====================================================
    # IDENTIFICATION
    # =====================================================

    "identify this",
    "identify the object",
    "identify the equipment",
    "identify what this is",
    "identify what is shown",
    "what is this object",
    "what object is this",
    "what thing is this",
    "what is shown here",
    "what is shown in this image",
    "what is shown in the image",
    "what is visible here",
    "what is visible in this image",
    "what is visible in the image",

    # =====================================================
    # PEOPLE
    # =====================================================

    "who is this",
    "who is in this image",
    "who is in the image",
    "is there a person",
    "is there a person in this image",
    "is there anyone in the image",
    "is this a person",
    "does this image contain a person",
    "does the image contain a person",
    "how many people are in the image",
    "how many people are visible",
    "what is the person doing",
    "what are the people doing",

    # =====================================================
    # OBJECTS
    # =====================================================

    "what objects are visible",
    "what objects are in the image",
    "what objects can you see",
    "list the objects in the image",
    "list the visible objects",
    "what items are shown",
    "what items are visible",
    "what things are visible",
    "what components are visible",
    "what parts are visible",
    "what is the main object",
    "what is the main thing in the image",
    "what is the main subject",

    # =====================================================
    # EQUIPMENT / MACHINERY
    # =====================================================

    "what equipment is this",
    "what equipment is shown",
    "which equipment is shown",
    "which equipment is this",
    "what machine is this",
    "what machine is shown",
    "which machine is shown",
    "what machinery is this",
    "what machinery is shown",
    "what type of equipment is this",
    "what type of machine is this",
    "what kind of equipment is shown",
    "what kind of machine is shown",
    "is this industrial equipment",
    "is this a machine",
    "is this industrial machinery",
    "what components does this equipment have",
    "what components are visible on this equipment",
    "what parts of the machine are visible",

    # =====================================================
    # VISUAL CONDITION
    # =====================================================

    "what condition is it in",
    "what condition is the equipment in",
    "what condition does it appear to be in",
    "does the equipment look damaged",
    "does the machine look damaged",
    "is there visible damage",
    "is there any visible damage",
    "do you see any damage",
    "do you see any visible damage",
    "are there any visible abnormalities",
    "are there any abnormalities",
    "does anything look unusual",
    "does anything look abnormal",
    "is anything unusual in the image",
    "is anything wrong in the image",
    "what abnormalities are visible",
    "what damage is visible",
    "what defects are visible",

    # =====================================================
    # LOCATION / POSITION
    # =====================================================

    "where is the object",
    "where is the equipment",
    "where is the machine",
    "where is the person",
    "where is the main object",
    "where are the components",
    "what is in the foreground",
    "what is in the background",
    "what is on the left",
    "what is on the right",
    "what is in the center",
    "what is in the middle",
    "what is at the top",
    "what is at the bottom",

    # =====================================================
    # COUNTING
    # =====================================================

    "how many objects are there",
    "how many objects are visible",
    "how many machines are there",
    "how many machines are visible",
    "how many pieces of equipment are shown",
    "how many components are visible",
    "how many parts are visible",
    "how many items are in the image",
    "how many people are there",
    "count the objects",
    "count the visible objects",
    "count the components",

    # =====================================================
    # COLORS / APPEARANCE
    # =====================================================

    "what color is it",
    "what color is the equipment",
    "what color is the machine",
    "what colors are visible",
    "what is the color of the object",
    "what does it look like",
    "what does the equipment look like",
    "what does the machine look like",
    "what is the appearance of the object",
    "describe the appearance",

    # =====================================================
    # TEXT / LABELS VISIBLE IN IMAGE
    # =====================================================

    "is there any text in the image",
    "is there text in the image",
    "what text is visible",
    "what text can you see",
    "what does the text say",
    "what does the label say",
    "what does this label say",
    "can you read the text",
    "can you read the label",
    "are there any labels",
    "what labels are visible",
    "what numbers are visible",
    "what words are visible",
    "what is written in the image",

    # =====================================================
    # SCENE / CONTEXT
    # =====================================================

    "what scene is shown",
    "what kind of scene is this",
    "what is happening in the image",
    "what is happening here",
    "what is going on in the image",
    "what is going on here",
    "where was this image taken",
    "what environment is shown",
    "what type of environment is this",
    "what surroundings are visible",
    "describe the surroundings",
    "describe the scene",

    # =====================================================
    # SIMPLE VISUAL CHECKS
    # =====================================================

    "is this a machine",
    "is this equipment",
    "is this a person",
    "is this an object",
    "is there a machine",
    "is there equipment",
    "is there a vehicle",
    "is there a building",
    "is there a warning sign",
    "is there a label",
    "is there a control panel",
    "is there a pipe",
    "is there a motor",
    "is there a pump",
    "is there a valve",

    # =====================================================
    # COMPARISON / VISUAL RELATIONSHIPS
    # =====================================================

    "what is the largest object",
    "what is the smallest object",
    "which object is largest",
    "which object is smallest",
    "which object is closest",
    "which object is farthest",
    "which component is visible",
    "which part is visible",
    "what is the most prominent object",
    "what is the main equipment shown",

    ]

    return any(
        phrase in q
        for phrase in image_phrases
    )

# =========================================================
# COMPANY-SCOPED DOCUMENT RETRIEVAL
# =========================================================

def _retrieve_company_documents(
    company,
    question,
    top_k=3
):
    print("\nSearching company documents...")
    print("Company:", company)

    from backend.integration.storage import company_paths
    from sentence_transformers import SentenceTransformer

    paths = company_paths(company)

    index_path = paths["faiss"]
    documents_path = paths["documents_pickle"]

    if not index_path.exists():
        print("Company FAISS index not found.")
        return []

    if not documents_path.exists():
        print("Company document metadata not found.")
        return []

    index = faiss.read_index(
        str(index_path)
    )

    with open(
        documents_path,
        "rb"
    ) as file:
        documents = pickle.load(file)

    if index.ntotal == 0:
        return []

    embedding_model = SentenceTransformer(
        "BAAI/bge-small-en-v1.5",
        local_files_only=True
    )

    query_embedding = embedding_model.encode(
        [question],
        normalize_embeddings=True
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )

    search_k = min(
        max(top_k * 5, 15),
        index.ntotal
    )

    scores, indices = index.search(
        query_embedding,
        search_k
    )

    candidates = []

    for score, index_position in zip(
        scores[0],
        indices[0]
    ):

        if index_position == -1:
            continue

        score = float(score)

        if score < MIN_SCORE:
            continue

        document = documents[index_position]

        candidates.append({
            "score": score,
            "text": document["text"],
            "source": document["metadata"]["source"],
            "page": document["metadata"]["page"]
        })

    # Keep the best chunk from each document first
    results = []
    sources_added = set()

    for candidate in candidates:

        source = candidate["source"]

        if source in sources_added:
            continue

        results.append(candidate)
        sources_added.add(source)

    # Add additional chunks if useful
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

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print("\nRetrieved company evidence:")
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

    return results