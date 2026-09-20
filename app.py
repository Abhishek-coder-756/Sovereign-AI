"""
Sovereign On-Premise Agentic AI Workbench — SIH26117
Root FastAPI entry point.

Run with:
    python3 app.py
or:
    uvicorn app:app --reload
"""

import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


# ================================================================
# FASTAPI IMPORTS
# ================================================================

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from fastapi.security import OAuth2PasswordRequestForm

from fastapi.responses import (
    FileResponse,
    JSONResponse,
)

from fastapi.staticfiles import StaticFiles

from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException


# ================================================================
# SECURITY
# ================================================================

from backend.app.security.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)

from backend.app.security.rbac import has_permission

from backend.app.security.audit import log_event


# ================================================================
# INTEGRATION
# ================================================================

from backend.integration.storage import company_paths

from backend.integration import (
    documents_registry,
    ingestion_service,
    rag_service,
    multimodal_service,
)

from backend.integration.rag_service import NoIndexError

from backend.integration import audit_reader

from typing import Optional
from backend.app.agents.workflow import build_agent
from backend.app.agents.conversation_store import ConversationStore, generate_title


# ================================================================
# APPLICATION & AGENT
# ================================================================

app = FastAPI(
    title="Sovereign On-Premise Agentic AI Workbench — SIH26117"
)

agent = build_agent()


# ================================================================
# SETTINGS
# ================================================================

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".md",
    ".text",
    ".log"
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp"
}

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


# ================================================================
# ERROR HANDLING
# ================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request,
    exc
):

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request data.",
            "errors": exc.errors()
        }
    )


# ================================================================
# AUTHENTICATION
# ================================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    user = authenticate_user(
        form_data.username,
        form_data.password
    )

    if not user:

        log_event(
            form_data.username,
            "",
            "LOGIN",
            "FAILED",
            "Invalid credentials"
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )

    token = create_access_token(
        {
            "sub": user["username"],
            "role": user["role"],
            "company": user["company"],
        }
    )

    log_event(
        user["username"],
        user["company"],
        "LOGIN",
        "SUCCESS"
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"],
        "company": user["company"],
    }


@app.get("/api/me")
def me(
    current_user: dict = Depends(get_current_user)
):

    return {
        "username": current_user["username"],
        "role": current_user["role"],
        "company": current_user["company"],
    }


# ================================================================
# HEALTH / SYSTEM STATUS
# ================================================================

def _check_ollama():

    try:

        import ollama

        response = ollama.list()

        models = [
            m.get("model") or m.get("name")
            for m in response.get("models", [])
        ]

        return {
            "reachable": True,
            "models": models,
            "text_model_available": any(
                "qwen2.5:3b" in (m or "")
                for m in models
            ),
            "vision_model_available": any(
                "llava:7b" in (m or "")
                for m in models
            ),
        }

    except Exception as e:

        return {
            "reachable": False,
            "models": [],
            "text_model_available": False,
            "vision_model_available": False,
            "error": str(e),
        }


def _importable(name: str) -> bool:

    try:

        __import__(name)

        return True

    except ImportError:

        return False


@app.get("/api/health")
def health():

    ollama_status = _check_ollama()

    return {

        "status": "ok",

        "local_llm_online":
            ollama_status["reachable"]
            and ollama_status["text_model_available"],

        "vision_model_online":
            ollama_status["reachable"]
            and ollama_status["vision_model_available"],

        "embeddings_loaded":
            _importable("sentence_transformers"),

        "faiss_ready":
            _importable("faiss"),

        "rag_ready":
            _importable("faiss")
            and _importable("sentence_transformers"),

        "evidence_checker_ready":
            True,

        "ollama":
            ollama_status,

        "network":
            "OFFLINE / LOCAL ONLY "
            "(configured for local processing; "
            "not a verified network probe)",
    }


# ================================================================
# DOCUMENT UPLOAD
# ================================================================

@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    if not has_permission(current_user["role"], "write"):
        log_event(
            current_user["username"],
            current_user["company"],
            "UPLOAD",
            "DENIED",
            file.filename
        )
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to upload files."
        )

    suffix = Path(file.filename).suffix.lower()

    if suffix in ALLOWED_DOCUMENT_EXTENSIONS:
        category = "document"
        dir_key = "documents"
    elif suffix in ALLOWED_IMAGE_EXTENSIONS:
        category = "image"
        dir_key = "images"
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type: {suffix}. "
                "Allowed documents: .pdf, .docx, .doc, .pptx, .ppt, .xlsx, .xls, .csv, .txt | Allowed images: .png, .jpg, .jpeg, .webp"
            )
        )

    contents = await file.read()

    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Upload failed: file exceeds the size limit."
        )

    company = current_user["company"]
    paths = company_paths(company)
    target_path = (
        paths[dir_key]
        / Path(file.filename).name
    )

    target_path.write_bytes(contents)

    record = documents_registry.register_upload(
        company,
        file.filename,
        category,
        len(contents)
    )

    log_event(
        current_user["username"],
        company,
        "UPLOAD",
        "SUCCESS",
        file.filename
    )

    # Attach to conversation if provided
    if conversation_id:
        if category == "document":
            ConversationStore.attach_file(
                company,
                current_user["username"],
                conversation_id,
                file.filename,
                str(target_path)
            )
            log_event(
                current_user["username"],
                company,
                "FILE_ATTACHED_TO_CONVERSATION",
                "SUCCESS",
                f"{file.filename} -> {conversation_id}"
            )
            # Automatically index uploaded document so RAG is immediately ready
            try:
                result = ingestion_service.ingest_company_documents(company)
                if result.get("indexed"):
                    rag_service.invalidate(company)
                    for f in result.get("per_file", []):
                        documents_registry.mark_indexed(
                            company,
                            f["filename"],
                            f["pages"],
                            f["chunks"]
                        )
                    record["indexed"] = True
            except Exception:
                pass
        else:
            ConversationStore.attach_image(
                company,
                current_user["username"],
                conversation_id,
                str(target_path),
                file.filename
            )
            log_event(
                current_user["username"],
                company,
                "IMAGE_ATTACHED_TO_CONVERSATION",
                "SUCCESS",
                f"{file.filename} -> {conversation_id}"
            )
        record["conversation_id"] = conversation_id

    return record



# ================================================================
# DOCUMENT LIST
# ================================================================

@app.get("/api/documents")
def get_documents(
    current_user: dict = Depends(get_current_user)
):

    return documents_registry.list_documents(
        current_user["company"]
    )


# ================================================================
# DOCUMENT INDEXING
# ================================================================

@app.post("/api/documents/index")
def index_documents(
    current_user: dict = Depends(get_current_user)
):

    if not has_permission(
        current_user["role"],
        "write"
    ):

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to index documents."
        )

    company = current_user["company"]

    start = time.time()

    result = ingestion_service.ingest_company_documents(
        company
    )

    execution_time = round(
        time.time() - start,
        3
    )

    if result["indexed"]:

        rag_service.invalidate(
            company
        )

        for f in result["per_file"]:

            documents_registry.mark_indexed(
                company,
                f["filename"],
                f["pages"],
                f["chunks"]
            )

    log_event(
        current_user["username"],
        company,
        "INDEX_DOCUMENTS",
        (
            "SUCCESS"
            if result["indexed"]
            else "NO_DOCUMENTS"
        ),
        (
            f"{result.get('documents', 0)} docs, "
            f"{result.get('chunks', 0)} chunks, "
            f"{execution_time}s"
        ),
    )

    return result


# ================================================================
# DOCUMENT DELETE
# ================================================================

@app.delete("/api/documents/{document_id}")
def delete_document(

    document_id: str,

    current_user: dict = Depends(
        get_current_user
    ),
):

    if not has_permission(
        current_user["role"],
        "write"
    ):

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete files."
        )

    company = current_user["company"]

    record = documents_registry.delete_document(
        company,
        document_id
    )

    if not record:

        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    dir_key = (
        "documents"
        if record["category"] == "document"
        else "images"
    )

    file_path = (
        company_paths(company)[dir_key]
        / record["filename"]
    )

    if file_path.exists():

        file_path.unlink()

    log_event(
        current_user["username"],
        company,
        "DELETE_DOCUMENT",
        "SUCCESS",
        record["filename"]
    )

    return {
        "deleted": True
    }


# ================================================================
# CONVERSATIONS (ChatGPT-Style Persistent Sessions)
# ================================================================

@app.get("/api/conversations")
def list_conversations(
    current_user: dict = Depends(get_current_user)
):
    company = current_user["company"]
    username = current_user["username"]
    convs = ConversationStore.list_conversations(company, username)
    log_event(username, company, "CONVERSATION_LOADED", "SUCCESS", f"{len(convs)} chats")
    return convs


@app.post("/api/conversations")
def create_conversation(
    payload: Optional[dict] = None,
    current_user: dict = Depends(get_current_user)
):
    company = current_user["company"]
    username = current_user["username"]
    title = (payload or {}).get("title", "New Chat")
    conv = ConversationStore.create_conversation(company, username, title=title)
    log_event(username, company, "CONVERSATION_CREATED", "SUCCESS", conv["conversation_id"])
    return conv


@app.get("/api/conversations/{conversation_id}")
def get_conversation_detail(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    company = current_user["company"]
    username = current_user["username"]
    conv = ConversationStore.get_conversation(company, username, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    company = current_user["company"]
    username = current_user["username"]
    ok = ConversationStore.delete_conversation(company, username, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found or could not be deleted.")
    log_event(username, company, "CONVERSATION_DELETED", "SUCCESS", conversation_id)
    return {"deleted": True, "conversation_id": conversation_id}


@app.delete("/api/conversations/{conversation_id}/attachments/{filename}")
def remove_conversation_attachment(
    conversation_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    company = current_user["company"]
    username = current_user["username"]
    conv = ConversationStore.remove_attachment(company, username, conversation_id, filename)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation or attachment not found.")
    return {
        "removed": True,
        "filename": filename,
        "uploaded_files": conv.get("uploaded_files", []),
        "uploaded_images": conv.get("uploaded_images", []),
    }


# ================================================================
# AGENTIC CHAT (LangGraph Orchestrated)
# ================================================================

@app.post("/api/chat")
def chat(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    if not has_permission(current_user["role"], "execute"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to query the AI."
        )

    message = (
        (payload or {}).get("message")
        or (payload or {}).get("query")
        or (payload or {}).get("question")
        or ""
    ).strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Message is required."
        )

    company = current_user["company"]
    username = current_user["username"]
    conversation_id = (payload or {}).get("conversation_id")

    # Resolve or create conversation
    conv = None
    if conversation_id:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
    if not conv:
        conv = ConversationStore.create_conversation(company, username, title=generate_title(message))
        conversation_id = conv["conversation_id"]

    # Check for active image in conversation
    active_image_path = ""
    uploaded_images = conv.get("uploaded_images", [])
    if uploaded_images:
        candidate = uploaded_images[-1]
        if Path(candidate).exists():
            active_image_path = candidate

    start = time.time()
    log_event(username, company, "AGENT_REQUEST", "RECEIVED", f"Conv {conversation_id}: {message[:60]}")

    # Build AgentState for LangGraph
    # Get the latest uploaded file path
    uploaded_files = conv.get("uploaded_files", [])
    active_file_path = ""

    if uploaded_files:
        candidate_file = uploaded_files[-1]
        if Path(candidate_file).exists():
            active_file_path = candidate_file

    state = {
        "conversation_id": conversation_id,
        "company": company,
        "username": username,
        "user_query": message,
        "image_path": active_image_path,
        "file_path": active_file_path,
        "uploaded_files": uploaded_files,
        "uploaded_images": conv.get("uploaded_images", []),
        "conversation_history": conv.get("messages", [])[-6:],
        "results": [],
        "plan": [],
        "sources": [],
        "agent_steps": [],
    }

    try:
        result_state = agent.invoke(state)
    except Exception as e:
        log_event(username, company, "AGENT_REQUEST", "FAILED", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Local AI agent error: {str(e)}"
        )

    execution_time = round(time.time() - start, 3)
    audit_id = uuid.uuid4().hex[:12]

    answer = result_state.get("final_answer", "")
    sources = result_state.get("sources", [])
    verification = result_state.get("verification", {})
    model_name = result_state.get("selected_model", "qwen2.5:3b")
    intent = result_state.get("intent", "general_local_chat")
    plan = result_state.get("plan", [])
    agent_steps = result_state.get("agent_steps", [])
    pdf_filename = result_state.get("pdf_filename", "")

    # Audit logging
    log_event(username, company, "AGENT_PLAN", intent, ", ".join(plan)[:120])
    log_event(username, company, "AGENT_RESPONSE", verification.get("status", "SUCCESS"), f"{message[:60]} ({execution_time}s)")

    # Save messages to conversation store
    meta = {
        "sources": sources,
        "verification": verification,
        "image_observation": result_state.get("image_observation"),
        "agent_used": True,
        "intent": intent,
        "plan": plan,
        "agent_steps": agent_steps,
        "model": model_name,
        "execution_time": execution_time,
        "audit_id": audit_id,
    }
    ConversationStore.add_message(company, username, conversation_id, "user", message)
    ConversationStore.add_message(company, username, conversation_id, "assistant", answer, metadata=meta)

    # Refetch updated conversation to return current attachments
    conv = ConversationStore.get_conversation(company, username, conversation_id)

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "sources": sources,
        "verification": verification,
        "model": model_name,
        "execution_time": execution_time,
        "audit_id": audit_id,
        "image_observation": result_state.get("image_observation"),
        "timings": result_state.get("timings"),
        "agent_used": True,
        "intent": intent,
        "source_scope": result_state.get("source_scope", "company"),
        "plan": plan,
        "selected_model": model_name,
        "selected_tool": result_state.get("selected_tool", ""),
        "agent_steps": agent_steps,
        "pdf_filename": pdf_filename,
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
    }


# ================================================================
# MULTIMODAL CHAT (LangGraph Orchestrated)
# ================================================================

@app.post("/api/chat/multimodal")
async def chat_multimodal(
    question: str = Form(...),
    top_k: int = Form(default=3),
    image: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    if not has_permission(current_user["role"], "execute"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to query the AI."
        )

    company = current_user["company"]
    username = current_user["username"]

    # Resolve or create conversation
    conv = None
    if conversation_id:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
    if not conv:
        conv = ConversationStore.create_conversation(company, username, title=generate_title(question))
        conversation_id = conv["conversation_id"]

    temp_path = None

    # Handle newly uploaded image if provided
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported image type: {suffix}"
            )
        contents = await image.read()
        if len(contents) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image upload failed: file exceeds size limit."
            )
        paths = company_paths(company)
        temp_path = paths["images"] / f"chat_{uuid.uuid4().hex[:8]}{suffix}"
        temp_path.write_bytes(contents)

        ConversationStore.attach_image(company, username, conversation_id, str(temp_path), image.filename)
        log_event(username, company, "IMAGE_ATTACHED_TO_CONVERSATION", "SUCCESS", f"{image.filename} -> {conversation_id}")
    else:
        # Fall back to image already attached to conversation
        if conv and conv.get("uploaded_images"):
            latest = conv["uploaded_images"][-1]
            if Path(latest).exists():
                temp_path = Path(latest)

    start = time.time()
    log_event(username, company, "AGENT_REQUEST", "RECEIVED", f"Conv {conversation_id} (multimodal): {question[:60]}")

    # Build AgentState for LangGraph
    state = {
        "conversation_id": conversation_id,
        "company": company,
        "username": username,
        "user_query": question,
        "image_path": str(temp_path) if temp_path else "",
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
        "conversation_history": conv.get("messages", [])[-6:] if conv else [],
        "results": [],
        "plan": [],
        "sources": [],
        "agent_steps": [],
    }

    try:
        result_state = agent.invoke(state)
    except Exception as e:
        log_event(username, company, "AGENT_REQUEST", "FAILED", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Local AI agent error: {str(e)}"
        )

    execution_time = round(time.time() - start, 3)
    audit_id = uuid.uuid4().hex[:12]

    answer = result_state.get("final_answer", "")
    sources = result_state.get("sources", [])
    verification = result_state.get("verification", {})
    model_name = result_state.get("selected_model", "llava:7b")
    intent = result_state.get("intent", "multimodal_rag")
    plan = result_state.get("plan", [])
    agent_steps = result_state.get("agent_steps", [])

    # Audit logging
    log_event(username, company, "AGENT_PLAN", intent, ", ".join(plan)[:120])
    log_event(username, company, "AGENT_RESPONSE", verification.get("status", "SUCCESS"), f"{question[:60]} ({execution_time}s)")

    # Save to conversation store
    meta = {
        "sources": sources,
        "verification": verification,
        "image_observation": result_state.get("image_observation"),
        "agent_used": True,
        "intent": intent,
        "plan": plan,
        "agent_steps": agent_steps,
        "model": model_name,
        "execution_time": execution_time,
        "audit_id": audit_id,
    }
    ConversationStore.add_message(company, username, conversation_id, "user", question)
    ConversationStore.add_message(company, username, conversation_id, "assistant", answer, metadata=meta)

    conv = ConversationStore.get_conversation(company, username, conversation_id)

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "image_observation": result_state.get("image_observation"),
        "sources": sources,
        "verification": verification,
        "model": model_name,
        "execution_time": execution_time,
        "timings": result_state.get("timings"),
        "audit_id": audit_id,
        "agent_used": True,
        "intent": intent,
        "source_scope": result_state.get("source_scope", "company"),
        "plan": plan,
        "selected_model": model_name,
        "selected_tool": result_state.get("selected_tool", ""),
        "agent_steps": agent_steps,
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
    }



# ================================================================
# VISION ANALYSIS
# ================================================================

@app.post("/api/vision/analyze")
async def vision_analyze(

    image: UploadFile = File(...),

    current_user: dict = Depends(
        get_current_user
    ),
):

    if not has_permission(
        current_user["role"],
        "execute"
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have permission "
                "to use vision analysis."
            )
        )

    suffix = Path(
        image.filename
    ).suffix.lower()

    if suffix not in ALLOWED_IMAGE_EXTENSIONS:

        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported image type: {suffix}"
            )
        )

    contents = await image.read()

    if len(contents) > MAX_UPLOAD_SIZE_BYTES:

        raise HTTPException(
            status_code=413,
            detail=(
                "Image upload failed: "
                "file exceeds size limit."
            )
        )

    company = current_user["company"]

    paths = company_paths(
        company
    )

    temp_path = (
        paths["images"]
        / f"vision_{uuid.uuid4().hex[:8]}{suffix}"
    )

    temp_path.write_bytes(
        contents
    )

    start = time.time()

    try:

        result = (
            multimodal_service
            .analyze_image_only(
                str(temp_path)
            )
        )

    except Exception as e:

        log_event(
            current_user["username"],
            company,
            "VISION_ANALYSIS",
            "FAILED",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Local AI service is unavailable. "
                "Please ensure Ollama is running."
            )
        )

    execution_time = round(
        time.time() - start,
        3
    )

    log_event(
        current_user["username"],
        company,
        "VISION_ANALYSIS",
        "SUCCESS",
        f"{execution_time}s"
    )

    return {

        "result":
            result,

        "model":
            "Qwen2.5-VL 3B",

        "execution_time":
            execution_time,
    }


# ================================================================
# AUDIT
# ================================================================

@app.get("/api/audit")
def get_audit(
    current_user: dict = Depends(
        get_current_user
    )
):

    if not has_permission(
        current_user["role"],
        "read"
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have permission "
                "to view the audit log."
            )
        )

    return audit_reader.list_events(
        company=current_user["company"]
    )


# ================================================================
# FRONTEND
# ================================================================

FRONTEND_DIR = (
    PROJECT_ROOT
    / "frontend"
)

app.mount(
    "/static",
    StaticFiles(
        directory=str(FRONTEND_DIR)
    ),
    name="static"
)


@app.get("/")
def index():

    return FileResponse(
        str(
            FRONTEND_DIR
            / "index.html"
        )
    )


@app.get("/style.css")
def style():

    return FileResponse(
        str(
            FRONTEND_DIR
            / "style.css"
        )
    )


@app.get("/script.js")
def script():

    return FileResponse(
        str(
            FRONTEND_DIR
            / "script.js"
        )
    )

# ================================================================
# GENERATED PDF DOWNLOAD
# ================================================================

@app.get("/generated-pdf/{filename}")
def download_generated_pdf(
    filename: str,
    current_user: dict = Depends(get_current_user),
):

    if not has_permission(
        current_user["role"],
        "execute"
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to download generated PDFs."
        )

    pdf_dir = (
        PROJECT_ROOT
        / "data"
        / "generated_pdfs"
    ).resolve()

    safe_filename = Path(filename).name

    pdf_path = (
        pdf_dir
        / safe_filename
    ).resolve()

    try:
        pdf_path.relative_to(pdf_dir)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Invalid PDF path."
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generated PDF not found."
        )

    log_event(
        current_user["username"],
        current_user["company"],
        "PDF_DOWNLOAD",
        "SUCCESS",
        safe_filename
    )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=safe_filename
    )


# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":

    import uvicorn

    print("\n" + "=" * 60)
    print("SOVEREIGN AI — SIH26117")
    print("=" * 60)

    print(
        "URL:      http://127.0.0.1:8000"
    )

    print(
        "Logins:   admin / admin123"
        "        (company: MRPL, role: admin)"
    )

    print(
        "          operator / operator123"
        "  (company: MRPL, role: operator)"
    )

    print(
        "          other_user / other123"
        "   (company: OTHER_COMPANY, role: admin)"
    )

    print("=" * 60 + "\n")

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )