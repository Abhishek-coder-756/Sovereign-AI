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
    Response,
)

from fastapi.staticfiles import StaticFiles

from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException


# ================================================================
# SECURITY
# ================================================================

import re
from pydantic import BaseModel, Field

from backend.app.security.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_admin_user,
)

from backend.app.security.passwords import (
    hash_password,
    validate_role_password,
)

from backend.app.security.users import (
    get_user,
    get_user_by_id,
    create_user,
    update_user_status,
    soft_delete_user,
    count_active_admins,
    list_company_users,
    get_company_user_stats,
    get_company_by_name,
    get_all_companies,
)

from backend.app.security.rbac import has_permission, is_admin

from backend.app.security.audit import log_event

from backend.app.security.migration import run_migrations



# ================================================================
# INTEGRATION
# ================================================================

from backend.integration.storage import company_paths
from typing import Optional, List, Dict, Any, Tuple
import logging

logger = logging.getLogger("uvicorn.error")


def resolve_company_file_path(company: str, filename: str) -> Optional[Path]:
    """
    Securely resolves a filename to a physical file within the company's storage.
    Enforces strict basename validation and path traversal prevention.
    The user can only access files strictly belonging to their company.
    """
    if not filename or not company:
        return None
    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        return None
    paths = company_paths(company)
    allowed_dirs = [paths["documents"].resolve(), paths["uploads"].resolve()]
    for d in allowed_dirs:
        candidate = (d / safe_name).resolve()
        try:
            candidate.relative_to(d)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


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

from db import get_connection
from backend.app.security.ssrf import (
    SSRFSecurityError,
    URLFetchTimeoutError,
    URLSizeLimitExceededError,
)
from backend.integration.web_fetcher import fetch_and_clean_public_url
from backend.integration.global_rag_service import (
    index_global_source,
    remove_global_source,
    get_conversation_sources,
)


# ================================================================
# APPLICATION & AGENT
# ================================================================

app = FastAPI(
    title="Sovereign On-Premise Agentic AI Workbench — SIH26117"
)

# Run safe database migrations on startup
try:
    run_migrations()
except Exception as _mig_err:
    print(f"[Startup] Migration notice: {_mig_err}")

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
# AUTHENTICATION & REGISTRATION
# ================================================================

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    mobile: str = Field(..., min_length=8, max_length=25)
    role: str = Field(...)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(...)
    company: Optional[str] = "MRPL"


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    try:
        user = authenticate_user(
            form_data.username,
            form_data.password
        )
    except HTTPException as e:
        # User credentials valid, but account is PENDING, REJECTED, or DISABLED!
        u_info = get_user(form_data.username)
        company_name = u_info["company"] if u_info else ""
        user_id = u_info["id"] if u_info else None
        role = u_info["role"] if u_info else None
        company_id = u_info["company_id"] if u_info else None

        log_event(
            username=form_data.username,
            company=company_name,
            action="LOGIN",
            status="FAILED",
            details=e.detail,
            user_id=user_id,
            target_role=role,
            company_id=company_id
        )
        raise e

    if not user:
        u_info = get_user(form_data.username)
        company_name = u_info["company"] if u_info else ""
        user_id = u_info["id"] if u_info else None
        role = u_info["role"] if u_info else None
        company_id = u_info["company_id"] if u_info else None

        log_event(
            username=form_data.username,
            company=company_name,
            action="LOGIN",
            status="FAILED",
            details="Invalid username or password",
            user_id=user_id,
            target_role=role,
            company_id=company_id
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
            "user_id": user["id"],
        }
    )

    log_event(
        username=user["username"],
        company=user["company"],
        action="LOGIN",
        status="SUCCESS",
        details=f"User {user['username']} signed in",
        user_id=user["id"],
        target_role=user["role"],
        company_id=user["company_id"]
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "name": user.get("name") or user["username"],
        "role": user["role"],
        "company": user["company"],
        "status": user.get("status", "APPROVED"),
    }


@app.post("/api/register")
def register_account(payload: RegisterRequest):
    name = payload.name.strip()
    username = payload.username.strip().lower()
    mobile = payload.mobile.strip()
    role = payload.role.strip().lower()
    password = payload.password
    confirm_password = payload.confirm_password
    company_name = (payload.company or "MRPL").strip()

    # 1. Name validation
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Full name must be at least 2 characters.")

    # 2. Username format validation
    if not re.match(r"^[a-z0-9_\-]+$", username):
        raise HTTPException(
            status_code=422,
            detail="Username can only contain alphanumeric characters, underscores, and hyphens."
        )

    # Check unique username
    existing = get_user(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken.")

    # 3. Mobile validation
    clean_mobile = re.sub(r"[\s\-\(\)]", "", mobile)
    if not re.match(r"^\+?[0-9]{10,15}$", clean_mobile):
        raise HTTPException(status_code=422, detail="Invalid mobile number format. Must be 10-15 digits.")

    # 4. Role validation
    if role not in ("admin", "operator", "employee"):
        raise HTTPException(
            status_code=422,
            detail="Invalid role selected. Allowed roles are: Admin, Operator, Employee."
        )

    # 5. Confirm password
    if password != confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")

    # 6. Role password prefix validation
    is_valid, prefix_err = validate_role_password(role, password) 
    if not is_valid:
        raise HTTPException(status_code=422, detail=prefix_err)

    # 7. Resolve company
    company_rec = get_company_by_name(company_name)
    if not company_rec:
        company_rec = get_company_by_name("MRPL")
    company_id = company_rec["id"] if company_rec else 1
    actual_company_name = company_rec["name"] if company_rec else "MRPL"

    # 8. Hash password and insert user with status PENDING
    hashed_pw = hash_password(password)
    user_id = create_user(
        username=username,
        name=name,
        mobile=mobile,
        role=role,
        company_id=company_id,
        hashed_password=hashed_pw,
        status="PENDING"
    )

    if not user_id:
        raise HTTPException(status_code=500, detail="Could not create user account. Please try again.")

    # 9. Audit event
    log_event(
        username=username,
        company=actual_company_name,
        action="USER_REGISTER",
        status="PENDING",
        details=f"New {role} registration submitted by {name} ({mobile})",
        user_id=user_id,
        target_user_id=user_id,
        target_username=username,
        target_role=role,
        company_id=company_id
    )

    return {
        "success": True,
        "message": "Registration submitted successfully. Your account is pending administrator approval.",
        "username": username,
        "status": "PENDING",
    }


@app.get("/api/companies")
def list_companies():
    return get_all_companies()


@app.get("/api/me")
def me(
    current_user: dict = Depends(get_current_user)
):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "name": current_user.get("name") or current_user["username"],
        "role": current_user["role"],
        "company": current_user["company"],
        "status": current_user.get("status", "APPROVED"),
    }


# ================================================================
# ADMIN PANEL (Protected by get_current_admin_user & Company Isolated)
# ================================================================

@app.get("/api/admin/stats")
def admin_stats(current_user: dict = Depends(get_current_admin_user)):
    return get_company_user_stats(current_user["company_id"])


@app.get("/api/admin/pending")
def admin_pending_users(current_user: dict = Depends(get_current_admin_user)):
    return list_company_users(current_user["company_id"], status="PENDING")


@app.get("/api/admin/users")
def admin_all_users(
    include_deleted: bool = False,
    current_user: dict = Depends(get_current_admin_user)
):
    return list_company_users(current_user["company_id"], include_deleted=include_deleted)


@app.post("/api/admin/users/{user_id}/approve")
def admin_approve_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin_user)
):
    target = get_user_by_id(user_id)
    if not target or target["company_id"] != current_user["company_id"]:
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    ok = update_user_status(user_id, "APPROVED", current_user["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to approve user.")

    log_event(
        username=current_user["username"],
        company=current_user["company"],
        action="USER_APPROVED",
        status="SUCCESS",
        details=f"Admin '{current_user['username']}' approved {target['role']} '{target['username']}'",
        user_id=current_user["id"],
        target_user_id=target["id"],
        target_username=target["username"],
        target_role=target["role"],
        company_id=current_user["company_id"]
    )
    return {"success": True, "message": f"User '{target['username']}' has been approved."}


@app.post("/api/admin/users/{user_id}/reject")
def admin_reject_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin_user)
):
    target = get_user_by_id(user_id)
    if not target or target["company_id"] != current_user["company_id"]:
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    ok = update_user_status(user_id, "REJECTED", current_user["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reject user.")

    log_event(
        username=current_user["username"],
        company=current_user["company"],
        action="USER_REJECTED",
        status="SUCCESS",
        details=f"Admin '{current_user['username']}' rejected {target['role']} '{target['username']}'",
        user_id=current_user["id"],
        target_user_id=target["id"],
        target_username=target["username"],
        target_role=target["role"],
        company_id=current_user["company_id"]
    )
    return {"success": True, "message": f"User '{target['username']}' registration was rejected."}


@app.post("/api/admin/users/{user_id}/disable")
def admin_disable_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin_user)
):
    target = get_user_by_id(user_id)
    if not target or target["company_id"] != current_user["company_id"]:
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    if target["role"] == "admin":
        if count_active_admins(current_user["company_id"]) <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last active administrator.")

    ok = update_user_status(user_id, "DISABLED", current_user["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to disable user.")

    log_event(
        username=current_user["username"],
        company=current_user["company"],
        action="USER_DISABLED",
        status="SUCCESS",
        details=f"Admin '{current_user['username']}' disabled {target['role']} '{target['username']}'",
        user_id=current_user["id"],
        target_user_id=target["id"],
        target_username=target["username"],
        target_role=target["role"],
        company_id=current_user["company_id"]
    )
    return {"success": True, "message": f"User '{target['username']}' has been disabled."}


@app.post("/api/admin/users/{user_id}/enable")
def admin_enable_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin_user)
):
    target = get_user_by_id(user_id)
    if not target or target["company_id"] != current_user["company_id"]:
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    ok = update_user_status(user_id, "APPROVED", current_user["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to enable user.")

    log_event(
        username=current_user["username"],
        company=current_user["company"],
        action="USER_ENABLED",
        status="SUCCESS",
        details=f"Admin '{current_user['username']}' enabled {target['role']} '{target['username']}'",
        user_id=current_user["id"],
        target_user_id=target["id"],
        target_username=target["username"],
        target_role=target["role"],
        company_id=current_user["company_id"]
    )
    return {"success": True, "message": f"User '{target['username']}' has been enabled."}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin_user)
):
    target = get_user_by_id(user_id)
    if not target or target["company_id"] != current_user["company_id"]:
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    if target["role"] == "admin":
        if count_active_admins(current_user["company_id"]) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active administrator.")

    ok = soft_delete_user(user_id, current_user["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to remove user.")

    log_event(
        username=current_user["username"],
        company=current_user["company"],
        action="USER_DELETED",
        status="SUCCESS",
        details=f"Admin '{current_user['username']}' removed {target['role']} '{target['username']}'",
        user_id=current_user["id"],
        target_user_id=target["id"],
        target_username=target["username"],
        target_role=target["role"],
        company_id=current_user["company_id"]
    )
    return {"success": True, "message": f"User '{target['username']}' removed successfully."}


@app.get("/api/admin/audit")
def admin_audit_log(current_user: dict = Depends(get_current_admin_user)):
    return audit_reader.list_events(company=current_user["company"])



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
                "qwen2.5vl" in (m or "")
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
                file.filename
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
            except Exception as e:
                logger.error(f"[UPLOAD INDEXING ERROR] Failed to index documents for {company}: {e}", exc_info=True)
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
# GLOBAL KNOWLEDGE SOURCES MANAGEMENT
# ================================================================

class AddGlobalSourceRequest(BaseModel):
    conversation_id: str
    url: str


@app.post("/api/global/sources")
def add_global_source(
    payload: AddGlobalSourceRequest,
    current_user: dict = Depends(get_current_user),
):
    if not has_permission(current_user["role"], "execute"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage Global sources."
        )

    company = current_user["company"]
    username = current_user["username"]
    conv_id = (payload.conversation_id or "").strip()
    raw_url = (payload.url or "").strip()

    if not raw_url:
        raise HTTPException(
            status_code=422,
            detail="URL is required."
        )

    # Resolve or create conversation
    conv = None
    if conv_id:
        conv = ConversationStore.get_conversation(company, username, conv_id)
    if not conv:
        conv = ConversationStore.create_conversation(company, username, title="Global Knowledge Chat")
        conv_id = conv["conversation_id"]

    log_event(username, company, "GLOBAL_SOURCE_ADDED", "PENDING", f"URL: {raw_url[:100]} -> Conv: {conv_id}")

    try:
        extracted = fetch_and_clean_public_url(raw_url, timeout=10)
    except SSRFSecurityError as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "BLOCKED_SSRF", f"{raw_url[:80]} ({str(e)})")
        raise HTTPException(status_code=400, detail=f"URL Security Block: {str(e)}")
    except URLFetchTimeoutError as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "TIMEOUT", str(e))
        raise HTTPException(status_code=504, detail="Network request timed out while fetching the public URL.")
    except URLSizeLimitExceededError as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "OVERSIZED", str(e))
        raise HTTPException(status_code=413, detail=str(e))
    except ValueError as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "UNREADABLE", str(e))
        raise HTTPException(status_code=422, detail="Unable to extract readable content from this URL.")
    except Exception as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "FAILED", str(e)[:120])
        raise HTTPException(status_code=502, detail=f"Failed to fetch public web page: {str(e)}")

    # Index into conversation-isolated FAISS store
    try:
        source_entry = index_global_source(
            conversation_id=conv_id,
            url=extracted["url"],
            title=extracted["title"],
            text=extracted["content"],
        )
    except Exception as e:
        log_event(username, company, "GLOBAL_SOURCE_FAILED", "INDEX_FAILED", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to index global source: {str(e)}")

    # Attach to conversation store
    ConversationStore.attach_global_source(company, username, conv_id, source_entry)

    # Persist in MySQL global_sources table if DB is available
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO global_sources (conversation_id, username, company_id, url, title, status, last_fetched_at)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE', NOW())
                """,
                (conv_id, username, current_user.get("company_id"), extracted["url"], extracted["title"][:500])
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as db_e:
            print(f"[GlobalSource DB insert notice] {db_e}")

    log_event(
        username=username,
        company=company,
        action="GLOBAL_SOURCE_FETCHED",
        status="SUCCESS",
        details=f"{extracted['title'][:50]} ({extracted['url'][:60]})",
    )

    return {
        "success": True,
        "conversation_id": conv_id,
        "source": source_entry,
        "global_sources": ConversationStore.get_global_sources(company, username, conv_id),
    }


@app.get("/api/global/sources")
def list_global_sources(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    company = current_user["company"]
    username = current_user["username"]
    sources = ConversationStore.get_global_sources(company, username, conversation_id)
    return {
        "conversation_id": conversation_id,
        "global_sources": sources,
    }


@app.delete("/api/global/sources/{source_id}")
def delete_global_source(
    source_id: str,
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    company = current_user["company"]
    username = current_user["username"]
    remove_global_source(conversation_id, source_id)
    ConversationStore.remove_global_source(company, username, conversation_id, source_id)
    log_event(username, company, "GLOBAL_SOURCE_REMOVED", "SUCCESS", f"Source {source_id} from {conversation_id}")
    return {
        "removed": True,
        "source_id": source_id,
        "global_sources": ConversationStore.get_global_sources(company, username, conversation_id),
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

    knowledge_mode = str((payload or {}).get("knowledge_mode") or "private").strip().lower()
    if knowledge_mode not in ("private", "global"):
        raise HTTPException(
            status_code=422,
            detail="Invalid knowledge_mode. Must be 'private' or 'global'."
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

    # Check for active file in conversation (securely resolved within company storage)
    active_file_path = ""
    uploaded_files = conv.get("uploaded_files", [])
    if uploaded_files:
        resolved = resolve_company_file_path(company, uploaded_files[-1])
        if resolved:
            active_file_path = str(resolved)

    file_exists = bool(active_file_path and Path(active_file_path).exists())
    file_type = Path(active_file_path).suffix.lower() if active_file_path else "none"
    print(
        f"[CHAT DEBUG]\nconversation_id={conversation_id}\ncompany={company}\n"
        f"uploaded_files={uploaded_files}\nresolved_file_path={active_file_path}\n"
        f"exists={file_exists}\nfile_type={file_type}\n[/CHAT DEBUG]"
    )

    start = time.time()
    log_event(username, company, "AGENT_REQUEST", "RECEIVED", f"Conv {conversation_id} [{knowledge_mode}]: {message[:60]}")

    # Build AgentState for LangGraph
    state = {
        "conversation_id": conversation_id,
        "company": company,
        "username": username,
        "user_query": message,
        "image_path": active_image_path,
        "file_path": active_file_path,
        "uploaded_files": conv.get("uploaded_files", []),
        "uploaded_images": conv.get("uploaded_images", []),
        "knowledge_mode": knowledge_mode,
        "global_sources": conv.get("global_sources", []),
        "conversation_history": conv.get("messages", [])[-6:],
        "results": [],
        "plan": [],
        "sources": [],
        "agent_steps": [],
    }

    try:
        result_state = agent.invoke(state)
        print(
            f"[CHAT DEBUG]\nintent={result_state.get('intent')}\n"
            f"selected_tool={result_state.get('selected_tool')}\n"
            f"selected_model={result_state.get('selected_model')}\n[/CHAT DEBUG]"
        )
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

    # Audit logging
    log_event(username, company, "AGENT_PLAN", intent, ", ".join(plan)[:120])
    if knowledge_mode == "global":
        log_event(username, company, "GLOBAL_QUERY", verification.get("status", "SUCCESS"), f"Conv {conversation_id}: {message[:60]} ({execution_time}s)")
    else:
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
        "knowledge_mode": knowledge_mode,
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
        "knowledge_mode": knowledge_mode,
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
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
        "global_sources": conv.get("global_sources", []) if conv else [],
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
    knowledge_mode: Optional[str] = Form("private"),
    current_user: dict = Depends(get_current_user),
):
    if not has_permission(current_user["role"], "execute"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to query the AI."
        )

    mode = str(knowledge_mode or "private").strip().lower()
    if mode not in ("private", "global"):
        raise HTTPException(
            status_code=422,
            detail="Invalid knowledge_mode. Must be 'private' or 'global'."
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

    # Check for active file in conversation (securely resolved within company storage)
    active_file_path = ""
    uploaded_files = conv.get("uploaded_files", []) if conv else []
    if uploaded_files:
        resolved = resolve_company_file_path(company, uploaded_files[-1])
        if resolved:
            active_file_path = str(resolved)

    start = time.time()
    log_event(username, company, "AGENT_REQUEST", "RECEIVED", f"Conv {conversation_id} (multimodal) [{mode}]: {question[:60]}")

    # Build AgentState for LangGraph
    state = {
        "conversation_id": conversation_id,
        "company": company,
        "username": username,
        "user_query": question,
        "image_path": str(temp_path) if temp_path else "",
        "file_path": active_file_path,
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
        "knowledge_mode": mode,
        "global_sources": conv.get("global_sources", []) if conv else [],
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
    model_name = result_state.get("selected_model", "qwen2.5vl:3b")
    intent = result_state.get("intent", "multimodal_rag")
    plan = result_state.get("plan", [])
    agent_steps = result_state.get("agent_steps", [])

    # Audit logging
    log_event(username, company, "AGENT_PLAN", intent, ", ".join(plan)[:120])
    if mode == "global":
        log_event(username, company, "GLOBAL_QUERY", verification.get("status", "SUCCESS"), f"Conv {conversation_id} (multimodal): {question[:60]} ({execution_time}s)")
    else:
        log_event(username, company, "AGENT_RESPONSE", verification.get("status", "SUCCESS"), f"{question[:60]} ({execution_time}s)")

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
        "knowledge_mode": mode,
        "execution_time": execution_time,
        "audit_id": audit_id,
    }
    ConversationStore.add_message(company, username, conversation_id, "user", question)
    ConversationStore.add_message(company, username, conversation_id, "assistant", answer, metadata=meta)

    # Refetch updated conversation to return current attachments
    conv = ConversationStore.get_conversation(company, username, conversation_id)

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "sources": sources,
        "verification": verification,
        "model": model_name,
        "knowledge_mode": mode,
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
        "uploaded_files": conv.get("uploaded_files", []) if conv else [],
        "uploaded_images": conv.get("uploaded_images", []) if conv else [],
        "global_sources": conv.get("global_sources", []) if conv else [],
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


NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/")
def root():
    return FileResponse(
        str(FRONTEND_DIR / "index.html"),
        headers=NO_CACHE_HEADERS,
    )


@app.get("/style.css")
def style():
    return FileResponse(
        str(FRONTEND_DIR / "style.css"),
        headers=NO_CACHE_HEADERS,
    )


@app.get("/script.js")
def script():
    return FileResponse(
        str(FRONTEND_DIR / "script.js"),
        headers=NO_CACHE_HEADERS,
    )


@app.get("/hybridaction/{path:path}")
def handle_browser_extension_noise(path: str):
    """Silently absorb third-party browser translation/tracker extension requests."""
    return Response(content="", media_type="application/javascript")


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