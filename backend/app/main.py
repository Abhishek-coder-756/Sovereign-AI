from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm

from .agents.workflow import build_agent

from .security.auth import (
    verify_password,
    create_access_token,
    get_current_user
)

from .security.users import get_user
from .security.rbac import has_permission
from .security.company import check_company_access
from .security.audit import log_event
from .security.sharing import create_share, check_share_access

from .tools.file_writer import write_file


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="SIH26117 AI Workbench"
)


# =========================================================
# CREATE AGENT
# =========================================================

agent = build_agent()


# =========================================================
# REQUEST MODELS
# =========================================================

class UserRequest(BaseModel):
    query: str
    image_path: str = ""


class WriteRequest(BaseModel):
    file_path: str
    content: str


class ShareRequest(BaseModel):
    resource: str
    shared_with: str
    expiry_minutes: int


# =========================================================
# HOME ENDPOINT
# =========================================================

@app.get("/")
def home():
    return {
        "message": "SIH26117 AI Workbench is running"
    }


# =========================================================
# LOGIN ENDPOINT
# =========================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    user = get_user(form_data.username)

    if not user:
        return {
            "error": "Invalid username or password"
        }

    if not verify_password(
        form_data.password,
        user["password"]
    ):
        return {
            "error": "Invalid username or password"
        }

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "company": user["company"]
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =========================================================
# PROTECTED AGENT ENDPOINT
# =========================================================

@app.post("/agent")
def run_agent(
    request: UserRequest,
    current_user: dict = Depends(get_current_user)
):

    # Check execute permission
    if not has_permission(
        current_user["role"],
        "execute"
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to execute the agent."
        )

    # Run LangGraph agent
    result = agent.invoke({
        "user_query": request.query,
        "image_path": request.image_path,
        "plan": [],
        "results": [],
        "final_answer": "",
        "result_checked": False
    })

    # Record successful agent execution
    log_event(
        current_user["username"],
        current_user["company"],
        "AGENT_EXECUTION",
        "SUCCESS",
        request.query
    )

    return {
        "query": request.query,
        "plan": result["plan"],
        "answer": result["final_answer"]
    }


# =========================================================
# PROTECTED FILE WRITING ENDPOINT
# =========================================================

@app.post("/write")
def write_data(
    request: WriteRequest,
    current_user: dict = Depends(get_current_user)
):

    # Check write permission
    if not has_permission(
        current_user["role"],
        "write"
    ):
        # Record denied write attempt
        log_event(
            current_user["username"],
            current_user["company"],
            "WRITE_FILE",
            "DENIED",
            "Insufficient permission"
        )

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to write files."
        )

    # Check company isolation
    check_company_access(
        current_user["company"],
        "MRPL"
    )

    # Write file
    result = write_file(
        request.file_path,
        request.content
    )

    # Record successful file write
    log_event(
        current_user["username"],
        current_user["company"],
        "WRITE_FILE",
        "SUCCESS",
        request.file_path
    )

    return {
        "message": result
    }


# =========================================================
# PROTECTED RESOURCE SHARING ENDPOINT
# =========================================================

@app.post("/share")
def share_resource(
    request: ShareRequest,
    current_user: dict = Depends(get_current_user)
):

    # Check write permission
    if not has_permission(
        current_user["role"],
        "write"
    ):
        # Record denied sharing attempt
        log_event(
            current_user["username"],
            current_user["company"],
            "SHARE_RESOURCE",
            "DENIED",
            "Insufficient permission"
        )

        raise HTTPException(
            status_code=403,
            detail="You do not have permission to share resources."
        )

    # Check company isolation
    check_company_access(
        current_user["company"],
        "MRPL"
    )

    # Create temporary share
    share = create_share(
        owner=current_user["username"],
        company=current_user["company"],
        resource=request.resource,
        shared_with=request.shared_with,
        expiry_minutes=request.expiry_minutes
    )

    # Record successful sharing
    log_event(
        current_user["username"],
        current_user["company"],
        "SHARE_RESOURCE",
        "SUCCESS",
        request.resource
    )

    return share


# =========================================================
# CHECK SHARED RESOURCE ACCESS
# =========================================================

@app.get("/share/access/{share_id:path}")
def access_shared_resource(
    share_id: str,
    current_user: dict = Depends(get_current_user)
):

    # Check whether the current user has access
    share = check_share_access(
        share_id,
        current_user["username"],
        current_user["company"]
    )

    # Record successful access
    log_event(
        current_user["username"],
        current_user["company"],
        "ACCESS_SHARED_RESOURCE",
        "SUCCESS",
        share["resource"]
    )

    return {
        "message": "Access granted",
        "resource": share["resource"],
        "shared_by": share["owner"],
        "expires_at": share["expires_at"].isoformat()
    }