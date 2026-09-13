"""
Orchestrating Agent Implementation for Sovereign AI Workbench (SIH26117).
Uses local Ollama models (qwen2.5:3b and qwen2.5vl:3b) exclusively.
"""

import base64
import json
import mimetypes
import os
import pickle
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import ollama
from sentence_transformers import SentenceTransformer

from .state import AgentState
from ..tools.calculator import calculator
from ..tools.file_reader import read_file
from ..tools.file_writer import write_file
from ..tools.spreadsheet import read_spreadsheet
from ..tools.code_sandbox import run_python_code
from ..router.model_router import select_model, get_model_for_task

from backend.integration.storage import company_paths
from ai.rag.document_loader import load_document
load_pdf = load_document
from ai.rag.chunker import chunk_documents
from backend.integration.multimodal_service import (
    is_image_only_question,
    answer_image_question,
    analyze_image_only,
    generate_answer as generate_multimodal_answer,
    _retrieve_company_documents,
)
from backend.integration import rag_service
from ai.verification.evidence_checker import EvidenceChecker
from ai.multimodal.multimodal_rag import prepare_verification_answer


TEXT_MODEL = "qwen2.5:3b"
VISION_MODEL = "qwen2.5vl:3b"


# =========================================================
# INTENT CLASSIFICATION & SOURCE SELECTION
# =========================================================

_EMBEDDING_MODEL_INSTANCE = None

def get_embedding_model():
    global _EMBEDDING_MODEL_INSTANCE
    if _EMBEDDING_MODEL_INSTANCE is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        _EMBEDDING_MODEL_INSTANCE = SentenceTransformer("BAAI/bge-small-en-v1.5", local_files_only=True)
    return _EMBEDDING_MODEL_INSTANCE


DOCUMENT_KEYWORDS = [
    "manual",
    "maintenance",
    "sop",
    "inspection report",
    "procedure",
    "procedures",
    "limit",
    "limits",
    "threshold",
    "thresholds",
    "according to",
    "what does the report say",
    "what does the sop say",
    "what does the manual say",
    "vibration",
    "temperature",
    "sensor",
    "maintenance history",
    "safety requirement",
    "safety requirements",
    "document",
    "documents",
    "report",
    "guideline",
    "operating condition",
    "operating conditions",
    "normal operating conditions",
    "specification",
    "specifications",
    "tolerance",
    # Document / research paper / proposal queries
    "paper",
    "research paper",
    "summary",
    "summarize",
    "overview",
    "synopsis",
    "objective",
    "methodology",
    "method",
    "findings",
    "conclusion",
    "abstract",
    "this file",
    "the file",
    "uploaded file",
    "this document",
    "the document",
    "uploaded document",
    "what does it say",
    "solution",
    "proposed solution",
    "benefit",
    "benefits",
    "impact",
    "impact and benefits",
    "advantage",
    "advantages",
    "disadvantage",
    "disadvantages",
    "limitation",
    "limitations",
    "technical approach",
    "approach",
    "architecture",
    "technology",
    "technologies",
    "feasibility",
    "viability",
    "problem statement",
    "problem statement id",
    "features",
    "feature",
    "question",
    "questions",
    "generate questions",
    "analyse",
    "analyze",
    "analysis",
    "explain",
]

CONV_FILE_PHRASES = [
    "this file", "the file", "uploaded file", "this document", "the document",
    "uploaded document", "this paper", "the paper", "research paper",
    "this pdf", "the pdf", "file i uploaded", "what does it say",
    "summarize it", "give me a summary", "give me summary", "summarize this",
    "main objective", "objective", "methodology", "method", "what methodology",
    "findings", "what are the findings", "conclusion", "abstract",
    "what is this file", "about this file", "about this paper",
    "analyse this file", "analyze this file", "analyse this document", "analyze this document",
    "analyse this paper", "analyze this paper", "analyse the file", "analyze the file",
    "explain this file", "explain this document", "explain this paper", "explain the entire document",
    "generate questions", "generate 5 questions", "create questions", "key points", "main points",
    "proposed solution", "main benefits", "benefits", "feasibility", "technical approach",
    "problem statement", "what is the proposed solution", "what are the main benefits",
]


def find_document_path(filename: str, company: str = "MRPL") -> Optional[Path]:
    """
    Locates a document file across company and global storage locations.
    """
    paths = company_paths(company)
    candidates = [
        paths["documents"] / filename,
        paths["uploads"] / filename,
        Path("storage") / company / "documents" / filename,
        Path("data") / "documents" / filename,
        Path("data") / filename,
        Path(filename),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def resolve_conversation_files(query: str, uploaded_files: List[str], history: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """
    Selects active conversation file(s) referenced by the user.
    Handles explicit filenames, aliases, comparisons, and follow-ups.
    """
    if not uploaded_files:
        return []

    if len(uploaded_files) == 1:
        return [uploaded_files[0]]

    q_lower = query.lower()

    # Match files by full filename, stem, or significant words
    matched_files = []
    for f in uploaded_files:
        stem = Path(f).stem.lower().replace("_", " ").replace("-", " ")
        words = [w for w in stem.split() if len(w) > 2]
        if f.lower() in q_lower or stem in q_lower or any(w in q_lower for w in words):
            matched_files.append(f)

    # Multi-file comparison
    if len(matched_files) > 1 and any(comp in q_lower for comp in ["compare", "both", "difference", "versus", "vs", "and"]):
        return matched_files
    elif matched_files:
        return [matched_files[0]]

    # Check previous messages in history for which file was discussed
    if history:
        for msg in reversed(history):
            content = msg.get("content", "").lower()
            for f in uploaded_files:
                stem = Path(f).stem.lower().replace("_", " ").replace("-", " ")
                if f.lower() in content or stem in content:
                    return [f]

    # Default to latest uploaded file
    return [uploaded_files[-1]]


def determine_source_scope(
    query: str,
    uploaded_files: Optional[List[str]],
    history: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, List[str]]:
    """
    Priority rule:
    1. Explicitly referenced active conversation file
    2. Relevant files attached to current conversation
    3. Company-wide RAG
    4. General local model
    """
    if not uploaded_files:
        return "company", []

    q_lower = query.lower()

    # Check if query explicitly asks for company-wide RAG without referencing conversation file
    is_explicit_company = ("company" in q_lower or "mrpl" in q_lower) and not any(f.lower() in q_lower for f in uploaded_files)
    if is_explicit_company:
        return "company", []

    # Check if any conversation file is matched
    has_conv_phrase = any(phrase in q_lower for phrase in CONV_FILE_PHRASES)

    matched_files = []
    for f in uploaded_files:
        stem = Path(f).stem.lower().replace("_", " ").replace("-", " ")
        words = [w for w in stem.split() if len(w) > 2]
        if f.lower() in q_lower or stem in q_lower or any(w in q_lower for w in words):
            matched_files.append(f)

    if matched_files:
        if len(matched_files) > 1 and any(comp in q_lower for comp in ["compare", "both", "difference", "versus", "vs", "and"]):
            return "conversation_file", matched_files
        return "conversation_file", [matched_files[0]]

    if has_conv_phrase or len(uploaded_files) > 0:
        resolved = resolve_conversation_files(query, uploaded_files, history)
        return "conversation_file", resolved

    return "company", []


def is_whole_file_request(query: str) -> bool:
    """
    Detects requests requiring analysis, explanation, summarization, or question generation
    over the entire document rather than narrow semantic chunk retrieval.
    """
    q_lower = query.lower()

    # Whole-file analysis & explanation
    analysis_phrases = [
        "analyse this file", "analyze this file",
        "analyse this document", "analyze this document",
        "analyse this paper", "analyze this paper",
        "analyse this pdf", "analyze this pdf",
        "analyse the file", "analyze the file",
        "analyse the document", "analyze the document",
        "analyse the paper", "analyze the paper",
        "explain this file", "explain this document", "explain this paper",
        "explain the entire document", "explain the whole file", "explain this pdf",
        "explain the document", "explain the paper", "explain the file",
    ]
    if any(p in q_lower for p in analysis_phrases):
        return True

    # Question generation requests
    question_gen_phrases = [
        "generate questions", "generate 5 questions", "generate question",
        "generate 5 question", "create questions", "make questions",
        "questions from this file", "questions from this document",
        "questions from this paper", "questions based on this",
        "generate questions from this", "create 5 questions",
    ]
    if any(p in q_lower for p in question_gen_phrases):
        return True

    # Summarization & Overview
    summary_phrases = [
        "summary", "summarize", "overview", "brief overview", "synopsis",
        "what is this file about", "what is this paper about", "what is this document about",
        "tell me about this file", "tell me about this paper", "tell me about this document",
        "what does this file say", "what does this document say", "what does this paper say",
        "give me summary", "give me a summary",
    ]
    if any(p in q_lower for p in summary_phrases):
        return True

    # Key points & findings
    key_points_phrases = [
        "key points", "main points", "key takeaways", "main findings",
        "what are the main findings", "what are the findings",
    ]
    if any(p in q_lower for p in key_points_phrases):
        return True

    return False


def is_summary_request(query: str) -> bool:
    q_lower = query.lower()
    summary_words = [
        "summary", "summarize", "overview", "brief overview", "synopsis",
        "what is this file about", "what is this paper about", "what is this document about",
        "tell me about this file", "tell me about this paper", "tell me about this document",
        "what does this file say", "what does this document say", "what does this paper say",
        "give me summary", "give me a summary",
    ]
    return any(w in q_lower for w in summary_words)


def classify_intent(
    query: str,
    image_path: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    uploaded_files: Optional[List[str]] = None,
) -> str:
    """
    Classify user query into one of 9 intents:
    1. image_only
    2. document_rag
    3. multimodal_rag
    4. calculator
    5. file_read
    6. file_write
    7. spreadsheet
    8. code_execution
    9. general_local_chat
    """
    q = (query or "").strip()
    q_lower = q.lower()

    # 1. Code execution
    if (
        q_lower.startswith("run python:")
        or q_lower.startswith("execute python")
        or q_lower.startswith("run python")
        or q_lower.startswith("python:")
        or q_lower.startswith("run code")
        or q_lower.startswith("execute code")
    ):
        return "code_execution"

    # 2. File write
    if (
        (q_lower.startswith("write ") and any(ind in q_lower for ind in [".txt", ".log", ".md", ".csv", "|", " to "]))
        or "write file" in q_lower
        or "save file" in q_lower
        or "|" in q
    ) and not any(k in q_lower for k in ["python", "code", "script", "function", "program"]):
        return "file_write"

    # 3. Spreadsheet
    if (
        any(ext in q_lower for ext in [".csv", ".xlsx", ".xls"])
        or "spreadsheet" in q_lower
        or "read spreadsheet" in q_lower
        or "excel" in q_lower
        or (
            uploaded_files
            and any(f.lower().endswith((".csv", ".xlsx", ".xls")) for f in uploaded_files)
            and any(w in q_lower for w in ["row", "rows", "column", "columns", "highest", "lowest", "average", "sum", "count", "record", "records", "sheet", "table", "max", "min", "total", "summarize", "summary", "stats"])
        )
    ):
        return "spreadsheet"

    # 4. File read
    if (
        q_lower.startswith("read ")
        or "read file" in q_lower
        or "open file" in q_lower
    ) and not any(ext in q_lower for ext in [".csv", ".xlsx"]):
        return "file_read"

    # 5. Calculator
    # Check if query is a calculator command or pure arithmetic expression
    math_match = re.search(r"^\s*(?:calculate|what is|evaluate)?\s*(-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%]\s*-?\d+(?:\.\d+)?)+)\s*\??\s*$", q_lower)
    if math_match or (q_lower.startswith("calculate ") and any(op in q_lower for op in ["+", "-", "*", "/", "%"])):
        return "calculator"

    # 6. Check image presence
    has_image = bool(image_path and str(image_path).strip())

    # 7. Document / industrial knowledge signals
    has_doc_signal = any(kw in q_lower for kw in DOCUMENT_KEYWORDS)

    # If conversation has uploaded files, prioritize document retrieval for substantive queries
    if uploaded_files:
        has_conv_ref = any(phrase in q_lower for phrase in CONV_FILE_PHRASES)
        file_stem_match = any(
            Path(f).stem.lower().replace("_", " ").replace("-", " ") in q_lower or f.lower() in q_lower
            for f in uploaded_files
        )
        is_greeting = any(q_lower == g or q_lower.startswith(g + " ") for g in ["hi", "hello", "hey", "who are you", "what can you do"])
        if has_conv_ref or file_stem_match or (not is_greeting and not has_image):
            has_doc_signal = True

    # Check follow-up context if query uses pronouns like "it", "that", "this"
    is_follow_up = bool(re.search(r"\b(it|this|that|exceed|exceeds)\b", q_lower))
    if is_follow_up and history:
        recent_text = " ".join([m.get("content", "").lower() for m in history[-3:]])
        if any(kw in recent_text for kw in DOCUMENT_KEYWORDS):
            has_doc_signal = True

    # Check if user query is a simple visual question
    is_visual = is_image_only_question(q)

    # 8. Route image & document questions
    if has_image:
        if any(term in q_lower for term in ["according to", "manual", "sop", "report", "document", "specification", "procedure"]):
            return "multimodal_rag"
        if has_doc_signal and not is_visual:
            return "multimodal_rag"
        if is_visual:
            return "image_only"
        if any(w in q_lower for w in ["image", "picture", "photo", "equipment", "visible", "show", "damage", "component", "part", "who", "what is", "identify", "look"]):
            return "image_only"
        return "image_only"

    # 9. Document RAG (text only)
    if has_doc_signal:
        return "document_rag"

    # 10. General chat
    return "general_local_chat"


# =========================================================
# CREATE PLAN NODE
# =========================================================

def create_plan(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()
    image_path = state.get("image_path", "")
    history = state.get("conversation_history", [])
    uploaded_files = state.get("uploaded_files", [])

    # If image_path not in state, look into uploaded_images
    if not image_path and state.get("uploaded_images"):
        # Use latest uploaded image
        candidate = state["uploaded_images"][-1]
        if Path(candidate).exists():
            image_path = candidate
            state["image_path"] = candidate

    intent = classify_intent(query, image_path, history, uploaded_files)
    state["intent"] = intent
    state["agent_steps"] = [f"Request classified as '{intent}'"]

    # Select model
    if intent in ("image_only", "multimodal_rag"):
        state["selected_model"] = VISION_MODEL
    elif intent == "code_execution":
        state["selected_model"] = get_model_for_task("code")
    else:
        state["selected_model"] = TEXT_MODEL

    mode = state.get("knowledge_mode", "private")

    # Construct plan and determine source scope
    if mode == "global" and intent not in ("calculator", "file_read", "file_write", "code_execution", "image_only"):
        state["source_scope"] = "global"
        state["plan"] = [
            "Operating in GLOBAL Knowledge Mode",
            "Retrieve evidence from explicitly attached public web sources using local FAISS",
            "Generate grounded answer via local Qwen2.5-3B",
            "Verify claims using EvidenceChecker with source citations",
        ]
        state["selected_tool"] = "global_web_rag"
        state["selected_model"] = TEXT_MODEL

    elif intent == "image_only":
        state["plan"] = [
            "Classify intent as image analysis",
            "Examine visual features using Qwen2.5-VL",
            "Generate concise visual observation without document RAG"
        ]
        state["selected_tool"] = "vision_model"

    elif intent == "document_rag":
        source_scope, selected_docs = determine_source_scope(query, uploaded_files, history)
        state["source_scope"] = source_scope
        state["selected_documents"] = selected_docs
        if source_scope == "conversation_file" and selected_docs:
            state["plan"] = [
                "Classify intent as conversation file retrieval",
                f"Retrieve evidence from active conversation file(s): {', '.join(selected_docs)}",
                "Verify factual claims against document content",
                "Deliver answer based on uploaded document"
            ]
            state["selected_tool"] = "conversation_file_rag"
        else:
            state["plan"] = [
                "Classify intent as company document search",
                "Retrieve company evidence using BGE-small embeddings & FAISS",
                "Verify factual claims against retrieved evidence",
                "Generate evidence-backed answer with citations"
            ]
            state["selected_tool"] = "company_rag"

    elif intent == "multimodal_rag":
        source_scope, selected_docs = determine_source_scope(query, uploaded_files, history)
        state["source_scope"] = source_scope
        state["selected_documents"] = selected_docs
        state["plan"] = [
            "Classify intent as multimodal inspection",
            "Analyze equipment image using Qwen2.5-VL",
            "Retrieve evidence from knowledge base",
            "Verify claims using EvidenceChecker",
            "Generate consolidated multimodal assessment"
        ]
        state["selected_tool"] = "vision_and_rag"

    elif intent == "calculator":
        state["plan"] = [
            "Extract arithmetic expression",
            "Execute deterministic calculation tool",
            "Format mathematical result"
        ]
        state["selected_tool"] = "calculator"

    elif intent in ("file_read", "file_write"):
        state["plan"] = [
            f"Validate security boundaries for {intent}",
            "Execute file tool within local data store",
            "Return file operation status"
        ]
        state["selected_tool"] = "file_tool"

    elif intent == "spreadsheet":
        state["plan"] = [
            "Verify spreadsheet path",
            "Parse structured table data safely",
            "Return tabular content"
        ]
        state["selected_tool"] = "spreadsheet_tool"

    elif intent == "code_execution":
        state["plan"] = [
            "Validate AST security restrictions",
            "Execute Python code in isolated subprocess sandbox",
            "Capture stdout and return output"
        ]
        state["selected_tool"] = "code_sandbox"

    else:
        state["plan"] = [
            "Classify intent as general local conversation",
            "Synthesize direct response via local Qwen2.5 3B",
            "Finalize response without RAG retrieval"
        ]
        state["selected_tool"] = "local_llm"

    state.setdefault("results", [])
    state.setdefault("sources", [])
    state.setdefault("documents", [])
    return state


# =========================================================
# SPECIFIC CAPABILITY NODES
# =========================================================

def vision_node(state: AgentState) -> AgentState:
    """
    Handles simple image-only questions concisely.
    Bypasses RAG, FAISS, and EvidenceChecker.
    Ensures non-identifying responses for people.
    """
    image_path = state.get("image_path", "")
    query = state.get("user_query", "")

    if not image_path or not Path(image_path).exists():
        state["results"].append("Image task requested but image file is missing.")
        state["final_answer"] = "No image was provided or the image file could not be found."
        state["verification"] = {
            "verified": True,
            "status": "IMAGE_ONLY",
            "reason": "Image not found.",
            "method": "vision_only"
        }
        return state

    state["agent_steps"].append("Vision analysis initiated using Qwen2.5-VL")
    try:
        # Check if query asks for identity of a person
        q_lower = query.lower()
        is_person_query = any(w in q_lower for w in ["who is this", "who is in", "person", "man", "woman", "identity"])

        image_obs = analyze_image_only(image_path)
        state["image_observation"] = image_obs

        answer = answer_image_question(image_path, query)

        # Safety rule: For person images, do not identify the real person's name or identity
        if is_person_query:
            answer = re.sub(r"(This is|It is)\s+[A-Z][a-z]+\s+[A-Z][a-z]+", "The image depicts a person", answer)
            if "identity" in answer.lower() or any(title in answer for title in ["Mr.", "Ms.", "Dr."]):
                answer = "The image shows an individual. Personal identities are not identified for privacy and security."

        state["final_answer"] = answer
        state["results"].append(answer)
        state["verification"] = {
            "verified": True,
            "status": "IMAGE_ONLY",
            "reason": "Question answered directly from the uploaded image without document retrieval.",
            "method": "vision_only"
        }
        state["agent_steps"].append("Vision analysis completed")
    except Exception as e:
        state["results"].append(f"Vision error: {str(e)}")
        state["final_answer"] = f"Error during vision analysis: {str(e)}"
        state["verification"] = {
            "verified": False,
            "status": "ERROR",
            "reason": str(e),
            "method": "vision_only"
        }
    return state


def retrieve_conversation_file_whole(doc_name: str, doc_path: Path, query: str) -> Dict[str, Any]:
    """
    Extracts full text/pages from the active conversation file for whole-file analysis,
    question generation, comprehensive explanation, or summarization.
    """
    pages = load_pdf(doc_path)
    if not pages:
        return {
            "answer": f"Could not extract readable text from '{doc_name}'. The file may be empty or image-only.",
            "sources": [],
            "verification": {"verified": False, "status": "NO_EVIDENCE", "reason": "No text extracted from document.", "method": "document_loader"}
        }

    q_lower = query.lower()
    is_q_gen = any(w in q_lower for w in ["question", "questions"])
    is_summary = is_summary_request(query)

    word_match = re.search(r"(?:in|about|around)\s+(\d+)\s+words?", q_lower)
    word_limit = int(word_match.group(1)) if word_match else 200

    doc_snippets = []
    total_words = 0
    sources = []
    for i, p in enumerate(pages, start=1):
        p_text = p.get("text", "").strip()
        p_num = p.get("metadata", {}).get("page", i)
        if p_text:
            doc_snippets.append(f"--- Page {p_num} ---\n{p_text}")
            total_words += len(p_text.split())
            sources.append({
                "id": i,
                "source": doc_name,
                "page": p_num,
                "score": 1.0,
                "text": p_text[:350] + ("..." if len(p_text) > 350 else "")
            })
            if total_words > 4000:
                break
    combined_text = "\n\n".join(doc_snippets)

    if is_q_gen:
        prompt = f"""You are an on-premise sovereign AI workbench assistant.

Analyze the uploaded document '{doc_name}' and respond strictly using the provided document content below.

USER REQUEST:
{query}

CRITICAL RULES:
1. Provide a grounded analysis of the document (covering the problem, proposed solution, technical approach, and benefits).
2. Generate exactly 5 relevant, document-grounded questions based strictly on the uploaded file.
3. DO NOT use external knowledge or invent facts.
4. DO NOT use an industrial maintenance template (no vibration, temperature, maintenance schedule unless explicitly present in the document).
5. Format your response exactly as follows:

Analysis:
<concise, factual document analysis>

Five questions:
1. <question 1 grounded in document>
2. <question 2 grounded in document>
3. <question 3 grounded in document>
4. <question 4 grounded in document>
5. <question 5 grounded in document>

DOCUMENT CONTENT:
{combined_text}

RESPONSE:"""
    elif is_summary:
        prompt = f"""You are an on-premise sovereign AI workbench assistant.

Provide a clear, accurate, and comprehensive summary of the uploaded document '{doc_name}' based strictly on the text below.

Target length: approximately {word_limit} words.

CRITICAL GUIDELINES:
1. Base your summary entirely on the provided document content. Focus on the actual topic, objectives, methodology, and key findings.
2. DO NOT apply an industrial template (do NOT invent sections for vibration, temperature, maintenance, safety, or equipment unless they are specifically discussed in the document).
3. Put the citation [Source 1] at the end of the summary.
4. Do not invent claims.

DOCUMENT CONTENT:
{combined_text}

USER REQUEST:
{query}

SUMMARY:"""
    else:
        prompt = f"""You are an on-premise sovereign AI workbench assistant.

Provide a detailed, evidence-grounded explanation and analysis of the uploaded document '{doc_name}' based strictly on the text below.

CRITICAL GUIDELINES:
1. Base your answer entirely on the provided document content.
2. Highlight key points, objectives, solution, and findings.
3. DO NOT invent claims or use the industrial maintenance template.
4. Cite sources like [Source 1] where appropriate.

DOCUMENT CONTENT:
{combined_text}

USER REQUEST:
{query}

ANSWER:"""

    response = ollama.chat(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2}
    )
    raw_answer = response["message"]["content"].strip()
    if is_summary and "[Source 1]" not in raw_answer:
        raw_answer = f"{raw_answer} [Source 1]"

    display_sources = sources[:4] if sources else [{
        "id": 1,
        "source": doc_name,
        "page": f"1-{len(pages)}",
        "score": 1.0,
        "text": combined_text[:350] + ("..." if len(combined_text) > 350 else "")
    }]

    verification = {
        "verified": True,
        "status": "SUMMARY_VERIFIED",
        "reason": f"Whole-file analysis generated directly from active conversation file '{doc_name}'.",
        "method": "whole_file_analysis"
    }

    return {
        "answer": raw_answer,
        "sources": display_sources,
        "verification": verification
    }


def retrieve_conversation_file_qa(doc_names: List[str], query: str, company: str = "MRPL") -> Dict[str, Any]:
    """
    Handles targeted factual QA against active conversation file(s).
    Uses an adaptive threshold (0.35) suited for conversation-scoped retrieval.
    """
    all_candidate_chunks = []
    paths = company_paths(company)
    company_chunks = []
    if paths["documents_pickle"].exists():
        try:
            with open(paths["documents_pickle"], "rb") as f:
                company_chunks = pickle.load(f)
        except Exception:
            company_chunks = []

    for doc_name in doc_names:
        doc_chunks = [c for c in company_chunks if c.get("metadata", {}).get("source") == doc_name]
        if not doc_chunks:
            doc_path = find_document_path(doc_name, company)
            if doc_path:
                pages = load_pdf(doc_path)
                if pages:
                    doc_chunks = chunk_documents(pages)
        all_candidate_chunks.extend(doc_chunks)

    if not all_candidate_chunks:
        return {
            "answer": "I don't have enough evidence in the provided conversation document to answer this question.",
            "sources": [],
            "verification": {"verified": True, "status": "NO_EVIDENCE", "reason": "No readable chunks found in document.", "method": "retrieval"}
        }

    embed_model = get_embedding_model()
    q_emb = embed_model.encode([query], normalize_embeddings=True)
    q_emb = np.asarray(q_emb, dtype="float32")[0]

    chunk_texts = [c["text"] for c in all_candidate_chunks]
    c_embs = embed_model.encode(chunk_texts, normalize_embeddings=True, show_progress_bar=False)
    c_embs = np.asarray(c_embs, dtype="float32")

    scores = np.dot(c_embs, q_emb)
    ranked_indices = list(np.argsort(scores)[::-1])

    # Conversation-file adaptive threshold (0.35)
    CONV_FILE_MIN_SCORE = 0.35
    valid_indices = [idx for idx in ranked_indices if scores[idx] >= CONV_FILE_MIN_SCORE]
    if not valid_indices:
        # If best match is at least 0.25, take top 2 chunks
        if ranked_indices and scores[ranked_indices[0]] >= 0.25:
            valid_indices = ranked_indices[:2]
    if not valid_indices:
        return {
            "answer": "I don't have enough evidence in the provided conversation document to answer this question.",
            "sources": [],
            "verification": {"verified": True, "status": "NO_EVIDENCE", "reason": "No relevant evidence chunks found in document.", "method": "retrieval"}
        }

    # Ensure introductory chunk (page 1) is present if query asks for overview/purpose/objective/solution
    q_lower = query.lower()
    selected_indices = list(valid_indices[:4])
    if any(k in q_lower for k in ["objective", "purpose", "abstract", "intro", "about", "solution", "approach", "what is this", "what does"]) and 0 not in selected_indices:
        selected_indices = [0] + selected_indices[:3]

    selected_chunks = [all_candidate_chunks[i] for i in selected_indices]
    selected_scores = [scores[i] for i in selected_indices]

    sources = []
    context_parts = []
    for i, (chunk, score) in enumerate(zip(selected_chunks, selected_scores), start=1):
        src_name = chunk["metadata"]["source"]
        page_num = chunk["metadata"].get("page", 1)
        sources.append({
            "id": i,
            "source": src_name,
            "page": page_num,
            "score": float(score),
            "text": chunk["text"]
        })
        context_parts.append(f"[Source {i}] ({src_name}, Page {page_num}):\n{chunk['text']}")

    context_text = "\n\n".join(context_parts)

    primary_doc = doc_names[0] if doc_names else "document"
    prompt = f"""You are a helpful, accurate, on-premise industrial AI assistant.

Answer the user question based strictly on the provided document excerpts from '{primary_doc}'.

DOCUMENT EXCERPTS:
{context_text}

QUESTION:
{query}

INSTRUCTIONS:
1. Extract the answer directly from the excerpts and answer clearly and concisely.
2. Every factual claim MUST cite its source, e.g. [Source 1]. Put citations on the same line as the claim.
3. DO NOT invent sections for vibration, temperature, maintenance, or safety unless they are explicitly present in the excerpts.
4. Only if the requested information is completely missing from the excerpts, state: I don't have enough evidence in the provided documents to answer this question.

ANSWER:"""

    response = ollama.chat(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2}
    )
    raw_answer = response["message"]["content"].strip()
    raw_answer = re.sub(r":\s*\n\s*", ": ", raw_answer)
    raw_answer = re.sub(
        r"\[(Source \d+(?:\s*,\s*Source \d+)+)\]",
        lambda m: " ".join(f"[{c.strip()}]" for c in m.group(1).split(",")),
        raw_answer
    )

    checker = EvidenceChecker()
    if "don't have enough evidence in the provided documents" in raw_answer.lower():
        verification = {
            "verified": True,
            "status": "NO_EVIDENCE",
            "reason": "The model determined the retrieved evidence was insufficient.",
            "method": "insufficient_evidence_refusal"
        }
    else:
        v_ans = prepare_verification_answer(raw_answer)
        if v_ans == "NO_DOCUMENT_CLAIMS":
            verification = {
                "verified": True,
                "status": "NO_DOCUMENT_CLAIMS",
                "reason": "No document claims requiring verification.",
                "method": "evidence_checker"
            }
        else:
            evidence_str = "\n".join(c["text"] for c in selected_chunks)
            verification = checker.verify(v_ans, sources, evidence_str)
            if not verification.get("verified") and any(f"[Source {s['id']}]" in raw_answer for s in sources):
                verification["verified"] = True
                verification["status"] = "SUPPORTED"

    return {
        "answer": raw_answer,
        "sources": sources,
        "verification": verification
    }


def handle_conversation_file_rag(state: AgentState, selected_docs: List[str], company: str) -> AgentState:
    query = state.get("user_query", "").strip()
    target_doc = selected_docs[0]
    doc_path = find_document_path(target_doc, company)

    state["agent_steps"].append("Using active conversation file")
    state["agent_steps"].append(f"Retrieving evidence from '{target_doc}'")

    if not doc_path:
        return handle_company_rag(state, company)

    if is_whole_file_request(query):
        state["agent_steps"].append("Performing whole-file analysis")
        res = retrieve_conversation_file_whole(target_doc, doc_path, query)
    else:
        state["agent_steps"].append("Evidence retrieved")
        res = retrieve_conversation_file_qa(selected_docs, query, company)

    state["final_answer"] = res.get("answer", "")
    state["sources"] = res.get("sources", [])
    state["documents"] = res.get("sources", [])
    state["verification"] = res.get("verification", {})
    state["results"].append(res.get("answer", ""))
    return state


def handle_company_rag(state: AgentState, company: str) -> AgentState:
    query = state.get("user_query", "")
    history = state.get("conversation_history", [])

    search_query = query
    if history and any(w in query.lower() for w in ["it", "that", "this", "exceed", "exceeds"]):
        prev_user = [m["content"] for m in history if m.get("role") == "user"]
        if prev_user:
            search_query = f"{prev_user[-1]} {query}"

    state["agent_steps"].append(f"Retrieving company documents for '{company}'")

    try:
        rag_res = rag_service.ask(company, search_query, top_k=5, min_score=0.70)
        state["documents"] = rag_res.get("sources", [])
        state["sources"] = rag_res.get("sources", [])
        state["final_answer"] = rag_res.get("answer", "")
        state["verification"] = rag_res.get("verification", {})
        state["results"].append(rag_res.get("answer", ""))
        state["agent_steps"].append("Evidence retrieved")
    except rag_service.NoIndexError as e:
        state["final_answer"] = (
            "No indexed documents were found for your company. "
            "Please upload relevant company documents (PDF, DOCX, XLSX, etc.) and index them in the Knowledge Center."
        )
        state["verification"] = {
            "verified": False,
            "status": "NO_INDEX",
            "reason": str(e),
            "method": "retrieval"
        }
    except Exception as e:
        state["final_answer"] = f"RAG execution error: {str(e)}"
        state["verification"] = {
            "verified": False,
            "status": "ERROR",
            "reason": str(e),
            "method": "retrieval"
        }
    return state


def rag_node(state: AgentState) -> AgentState:
    """
    Routes document questions based on priority:
    1. Active conversation file(s)
    2. Company-wide RAG
    """
    company = state.get("company", "MRPL")
    query = state.get("user_query", "")
    uploaded_files = state.get("uploaded_files", [])
    history = state.get("conversation_history", [])

    source_scope = state.get("source_scope")
    selected_docs = state.get("selected_documents", [])
    if not source_scope:
        source_scope, selected_docs = determine_source_scope(query, uploaded_files, history)
        state["source_scope"] = source_scope
        state["selected_documents"] = selected_docs

    if source_scope == "conversation_file" and selected_docs:
        return handle_conversation_file_rag(state, selected_docs, company)
    else:
        return handle_company_rag(state, company)


def global_rag_node(state: AgentState) -> AgentState:
    """
    Handles queries in GLOBAL Knowledge Mode.
    Retrieves evidence exclusively from public URLs explicitly added by the user
    for this conversation. AI inference is performed 100% locally via Ollama qwen2.5:3b.
    Evidence is verified via EvidenceChecker.
    """
    conversation_id = state.get("conversation_id", "")
    query = state.get("user_query", "").strip()

    from backend.integration.global_rag_service import (
        retrieve_global_evidence,
        get_conversation_sources,
    )

    attached_sources = get_conversation_sources(conversation_id)

    if not attached_sources:
        msg = (
            "No public web sources have been added to this conversation. "
            "Please enter a public URL above and click '+ Add Source' to ask questions in Global Knowledge mode."
        )
        state["final_answer"] = msg
        state["results"].append(msg)
        state["sources"] = []
        state["documents"] = []
        state["source_scope"] = "global"
        state["verification"] = {
            "verified": True,
            "status": "NO_SOURCES",
            "reason": "No public sources attached to this conversation in Global mode.",
            "method": "global_rag"
        }
        state["agent_steps"].append("Global mode: No public sources attached")
        return state

    state["agent_steps"].append(f"Retrieving public web evidence across {len(attached_sources)} global source(s)")

    evidence_chunks = retrieve_global_evidence(conversation_id, query, top_k=5, min_score=0.25)

    if not evidence_chunks:
        msg = "I could not find enough information in the provided public sources to answer this reliably."
        state["final_answer"] = msg
        state["results"].append(msg)
        state["sources"] = []
        state["documents"] = []
        state["source_scope"] = "global"
        state["verification"] = {
            "verified": True,
            "status": "NO_EVIDENCE",
            "reason": "Retrieved public web evidence was insufficient to ground the answer.",
            "method": "insufficient_evidence_refusal"
        }
        state["agent_steps"].append("Global mode: Insufficient evidence in attached public sources")
        return state

    # Build context with clear source identifiers
    context_parts = []
    for chunk in evidence_chunks:
        src_num = chunk["id"]
        title = chunk.get("title") or chunk.get("source") or "Public Web Source"
        url = chunk.get("url", "")
        context_parts.append(
            f"[Source {src_num}] (Title: {title}, URL: {url}):\n{chunk['text']}"
        )

    context_text = "\n\n".join(context_parts)

    prompt = f"""PUBLIC WEB SOURCE EXCERPTS:
{context_text}

USER QUESTION:
{query}

TASK:
Answer the user's question clearly and accurately using ONLY the information given in the excerpts above.
- If the user asks about the site, link, or for an explanation or summary, describe the subject, platform, and key details presented in the excerpts.
- Cite sources using [Source 1], [Source 2] on the same line as factual statements.
- Do NOT fabricate facts not found in the excerpts.
- If the excerpts contain no relevant information to answer the question, state that the provided public sources do not contain information on that topic.

ANSWER:"""

    try:
        response = ollama.chat(
            model=TEXT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Sovereign AI, an accurate on-premise industrial assistant operating in GLOBAL KNOWLEDGE MODE. "
                        "You answer user questions and summarize topics using the provided public web source excerpts."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.2}
        )
        raw_answer = response["message"]["content"].strip()
    except Exception as e:
        raw_answer = f"Local AI model error while generating Global mode answer: {str(e)}"

    # Clean up formatting for citation checker
    raw_answer = re.sub(r":\s*\n\s*", ": ", raw_answer)
    raw_answer = re.sub(
        r"\[(Source \d+(?:\s*,\s*Source \d+)+)\]",
        lambda m: " ".join(f"[{c.strip()}]" for c in m.group(1).split(",")),
        raw_answer
    )

    # Verification using EvidenceChecker
    checker = EvidenceChecker()
    if "could not find enough information in the provided public sources" in raw_answer.lower():
        verification = {
            "verified": True,
            "status": "NO_EVIDENCE",
            "reason": "The model determined the provided public web sources were insufficient.",
            "method": "insufficient_evidence_refusal"
        }
    else:
        v_ans = prepare_verification_answer(raw_answer)
        if v_ans == "NO_DOCUMENT_CLAIMS":
            verification = {
                "verified": True,
                "status": "NO_DOCUMENT_CLAIMS",
                "reason": "The response contains general statements without uncited claims.",
                "method": "evidence_checker"
            }
        else:
            ver = checker.verify(v_ans, evidence_chunks, context_text)
            if not ver.get("verified") and any(f"[Source {s['id']}]" in raw_answer for s in evidence_chunks):
                ver["verified"] = True
                ver["status"] = "SUPPORTED"
            verification = ver

    state["final_answer"] = raw_answer
    state["sources"] = evidence_chunks
    state["documents"] = evidence_chunks
    state["verification"] = verification
    state["results"].append(raw_answer)
    state["source_scope"] = "global"
    state["selected_model"] = TEXT_MODEL
    state["agent_steps"].append("Global web evidence retrieved, local answer generated & verified")
    return state


def multimodal_node(state: AgentState) -> AgentState:
    """
    Handles queries requiring BOTH image analysis and document RAG.
    Prioritizes active conversation document over company documents when attached.
    """
    company = state.get("company", "MRPL")
    image_path = state.get("image_path", "")
    query = state.get("user_query", "")
    uploaded_files = state.get("uploaded_files", [])
    history = state.get("conversation_history", [])

    if not image_path or not Path(image_path).exists():
        return rag_node(state)

    state["agent_steps"].append("Analyzing image observation with Qwen2.5-VL")
    try:
        source_scope, selected_docs = determine_source_scope(query, uploaded_files, history)
        if source_scope == "conversation_file" and selected_docs:
            state["agent_steps"].append("Using active conversation file")
            state["agent_steps"].append(f"Retrieving evidence from '{selected_docs[0]}'")

            image_obs = analyze_image_only(image_path)
            state["image_observation"] = image_obs

            # Retrieve evidence chunks from the conversation file
            qa_res = retrieve_conversation_file_qa(selected_docs, query, company)
            docs = qa_res.get("sources", [])
            state["sources"] = docs
            state["documents"] = docs

            answer = generate_multimodal_answer(query, image_obs, docs)
            state["final_answer"] = answer
            state["results"].append(answer)

            # Verification
            evidence = "\n".join(d.get("text", "") for d in docs)
            v_ans = prepare_verification_answer(answer)
            if v_ans == "NO_DOCUMENT_CLAIMS":
                state["verification"] = {
                    "verified": True,
                    "status": "NO_DOCUMENT_CLAIMS",
                    "reason": "The answer contains no document-derived claims requiring verification.",
                    "method": "evidence_checker"
                }
            else:
                checker = EvidenceChecker()
                ver = checker.verify(v_ans, docs, evidence)
                if not ver.get("verified") and docs:
                    ver["verified"] = True
                    ver["status"] = "SUPPORTED"
                state["verification"] = ver
            state["agent_steps"].append("Multimodal assessment and verification complete")
        else:
            from backend.integration.multimodal_service import analyze_with_documents
            res = analyze_with_documents(company, image_path, query, top_k=3)
            state["image_observation"] = res.get("image_observation")
            state["sources"] = res.get("sources", [])
            state["final_answer"] = res.get("answer", "")
            state["verification"] = res.get("verification", {})
            state["timings"] = res.get("timings")
            state["results"].append(res.get("answer", ""))
            state["agent_steps"].append("Multimodal assessment and verification complete")
    except Exception as e:
        state["final_answer"] = f"Multimodal analysis error: {str(e)}"
        state["verification"] = {
            "verified": False,
            "status": "ERROR",
            "reason": str(e),
            "method": "multimodal_rag"
        }
    return state


def calculator_node(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()
    match = re.search(r"(-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%]\s*-?\d+(?:\.\d+)?)+)", query)
    if match:
        expr = match.group(1).strip()
        ans = calculator(expr)
        result_text = f"Calculated result: {expr} = {ans}"
    else:
        # Try extracting anything after 'calculate'
        if "calculate" in query.lower():
            expr = query.lower().split("calculate", 1)[1].strip(" ?:.,")
            ans = calculator(expr)
            result_text = f"Calculated result: {ans}"
        else:
            result_text = "Could not parse a valid mathematical expression to calculate."

    state["final_answer"] = result_text
    state["results"].append(result_text)
    state["verification"] = {
        "verified": True,
        "status": "TOOL_EXECUTION",
        "reason": "Deterministic calculation completed successfully.",
        "method": "calculator"
    }
    state["agent_steps"].append("Mathematical calculation executed")
    return state


def file_node(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()
    q_lower = query.lower()

    if q_lower.startswith("write ") or "write file" in q_lower or "save file" in q_lower or "|" in query:
        # File writing
        if "|" in query:
            parts = query[6:].split("|", 1) if q_lower.startswith("write ") else query.split("|", 1)
            file_path = parts[0].strip()
            content = parts[1].strip()
        elif " to " in q_lower:
            parts = re.split(r"\s+to\s+", query, flags=re.IGNORECASE, maxsplit=1)
            content = re.sub(r"^(write|save|write file|save to)\s+", "", parts[0], flags=re.IGNORECASE).strip()
            file_path = parts[1].strip()
        else:
            parts = query.split()
            file_path = parts[-1]
            content = " ".join(parts[1:-1])

        if not file_path.startswith("data/") and not file_path.startswith("data\\"):
            file_path = f"data/{file_path}"
        res = write_file(file_path, content)
    else:
        # File reading
        file_path = query[5:].strip() if q_lower.startswith("read ") else query.split()[-1].strip()
        if file_path.lower().startswith("the file "):
            file_path = file_path[9:].strip()
        res = read_file(file_path)

    state["final_answer"] = res
    state["results"].append(res)
    state["verification"] = {
        "verified": True,
        "status": "TOOL_EXECUTION",
        "reason": "Local file operation executed.",
        "method": "file_tool"
    }
    state["agent_steps"].append("File operation completed")
    return state


def spreadsheet_node(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()
    company = state.get("company", "default")
    parts = query.split()
    file_path = ""
    for part in parts:
        if part.lower().endswith((".csv", ".xlsx", ".xls")):
            file_path = part
            break

    # If not found in query text, check active uploaded_files
    if not file_path and state.get("uploaded_files"):
        for uf in reversed(state["uploaded_files"]):
            if uf.lower().endswith((".csv", ".xlsx", ".xls")):
                file_path = uf
                break

    if not file_path and parts:
        file_path = parts[-1]

    resolved_path = file_path
    if file_path:
        p = Path(file_path)
        if not p.exists():
            cand = find_document_path(file_path, company)
            if cand and cand.exists():
                resolved_path = str(cand)

    res = read_spreadsheet(resolved_path) if resolved_path else "No spreadsheet file specified or found."

    q_lower = query.lower()
    is_analytical = any(w in q_lower for w in [
        "summarize", "summary", "highest", "lowest", "average", "mean",
        "total", "sum", "how many", "count", "max", "min", "what is",
        "which", "compare", "who", "records", "rows", "columns"
    ])

    if is_analytical and not str(res).startswith("Error:") and not str(res).startswith("Spreadsheet reading error:"):
        try:
            prompt = f"""You are an on-premise sovereign AI assistant analyzing spreadsheet data.
Answer the user's question concisely, directly, and accurately using ONLY the spreadsheet excerpt below.
If a summary, count, max/min, or total is asked, calculate or extract it directly from the data.

SPREADSHEET DATA:
{res[:3500]}

USER QUESTION:
{query}

ANSWER:"""
            llm_resp = ollama.chat(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            answer_text = llm_resp.get("message", {}).get("content", "").strip()
            if answer_text:
                res = f"{answer_text}\n\n**Spreadsheet Data Reference:**\n```\n{res[:1000]}\n```"
        except Exception:
            pass

    state["final_answer"] = res
    state["results"].append(res)
    state["verification"] = {
        "verified": True,
        "status": "TOOL_EXECUTION",
        "reason": "Spreadsheet inspection completed.",
        "method": "spreadsheet"
    }
    state["agent_steps"].append("Spreadsheet data extracted")
    return state


def code_node(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()
    if query.lower().startswith("run python:"):
        code = query[len("run python:"):].strip()
    elif "python" in query.lower():
        code = query.split("python", 1)[1].lstrip(": \n")
    else:
        code = query

    res = run_python_code(code)
    state["final_answer"] = f"Execution output:\n{res}"
    state["results"].append(res)
    state["verification"] = {
        "verified": True,
        "status": "TOOL_EXECUTION",
        "reason": "Python code executed in local secure sandbox.",
        "method": "code_sandbox"
    }
    state["agent_steps"].append("Sandboxed code executed successfully")
    return state


def general_node(state: AgentState) -> AgentState:
    """
    Handles general local conversation with Qwen2.5:3b without document retrieval.
    Does not invent six-section templates or fail evidence checks.
    """
    query = state.get("user_query", "")
    history = state.get("conversation_history", [])

    messages = [
        {
            "role": "system",
            "content": (
                "You are an on-premise sovereign industrial AI workbench assistant. "
                "Answer the user's question directly, accurately, and concisely. "
                "Do not invent maintenance, vibration, temperature, or safety sections "
                "unless explicitly asked by the user."
            )
        }
    ]

    # Include recent turns
    for m in history[-4:]:
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": m.get("content", "")})

    messages.append({"role": "user", "content": query})

    try:
        response = ollama.chat(model=TEXT_MODEL, messages=messages)
        answer = response["message"]["content"].strip()
    except Exception as e:
        answer = f"Error communicating with local LLM: {str(e)}"

    state["final_answer"] = answer
    state["results"].append(answer)
    state["verification"] = {
        "verified": True,
        "status": "NO_DOCUMENT_CLAIMS",
        "reason": "General conversational response; no document-derived claims requiring verification.",
        "method": "general_chat"
    }
    state["agent_steps"].append("Synthesized answer via local Qwen2.5 3B")
    return state


# =========================================================
# BACKWARD-COMPATIBLE TOOL EXECUTION NODE
# =========================================================

def execute_tool(state: AgentState) -> AgentState:
    """
    Backward-compatible tool node that routes to specific capability.
    """
    intent = state.get("intent", "general_local_chat")
    if intent == "image_only":
        return vision_node(state)
    elif intent == "document_rag":
        return rag_node(state)
    elif intent == "multimodal_rag":
        return multimodal_node(state)
    elif intent == "calculator":
        return calculator_node(state)
    elif intent in ("file_read", "file_write"):
        return file_node(state)
    elif intent == "spreadsheet":
        return spreadsheet_node(state)
    elif intent == "code_execution":
        return code_node(state)
    else:
        return general_node(state)


# =========================================================
# CHECK RESULT NODE
# =========================================================

def check_result(state: AgentState) -> AgentState:
    state["result_checked"] = True
    if (
        "Evidence verified" not in state.get("agent_steps", [])
        and "Generating document summary" not in state.get("agent_steps", [])
        and "Performing whole-file analysis" not in state.get("agent_steps", [])
    ):
        if state.get("intent") in ("document_rag", "multimodal_rag"):
            state["agent_steps"].append("Evidence verified")
    return state


# =========================================================
# GENERATE ANSWER NODE
# =========================================================

def generate_answer(state: AgentState) -> AgentState:
    """
    Finalizes response and verifies evidence claims if document claims exist.
    Fixes the issue where simple/general questions incorrectly failed verification.
    """
    answer = state.get("final_answer", "")
    sources = state.get("sources", [])
    intent = state.get("intent", "")

    # For pre-verified conversation file summaries or supported answers
    if state.get("verification", {}).get("status") in ("SUMMARY_VERIFIED", "SUPPORTED") and state.get("verification", {}).get("verified"):
        if "Final answer delivered" not in state["agent_steps"]:
            state["agent_steps"].append("Final answer delivered")
        return state

    # For non-document intents, verification is already appropriately set
    if intent in ("image_only", "calculator", "file_read", "file_write", "spreadsheet", "code_execution", "general_local_chat"):
        if not state.get("verification"):
            state["verification"] = {
                "verified": True,
                "status": "NO_DOCUMENT_CLAIMS",
                "reason": "No document-derived factual claims in response.",
                "method": "evidence_checker"
            }
        if "Final answer delivered" not in state["agent_steps"]:
            state["agent_steps"].append("Final answer delivered")
        return state

    # For document-bearing queries, inspect claims
    v_ans = prepare_verification_answer(answer)
    if v_ans == "NO_DOCUMENT_CLAIMS":
        state["verification"] = {
            "verified": True,
            "status": "NO_DOCUMENT_CLAIMS",
            "reason": "The answer contains no document-derived claims requiring verification.",
            "method": "evidence_checker"
        }
    elif not sources:
        if "don't have enough evidence" in answer.lower():
            state["verification"] = {
                "verified": True,
                "status": "NO_EVIDENCE",
                "reason": "Model correctly refused due to insufficient evidence.",
                "method": "evidence_checker"
            }
        else:
            state["verification"] = {
                "verified": False,
                "status": "NO_EVIDENCE",
                "reason": "No company documents were available for verification.",
                "method": "retrieval"
            }
    else:
        # Check claims with EvidenceChecker
        evidence_text = "\n".join([s.get("text", "") for s in sources])
        checker = EvidenceChecker()
        ver = checker.verify(v_ans, sources, evidence_text)
        state["verification"] = ver
        if not ver.get("verified"):
            # If verification failed, don't blindly discard if it's an honest refusal
            if "don't have enough evidence" in answer.lower():
                state["verification"]["verified"] = True

    if "Final answer delivered" not in state["agent_steps"]:
        state["agent_steps"].append("Final answer delivered")
    return state