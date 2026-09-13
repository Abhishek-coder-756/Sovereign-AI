from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os

from dotenv import load_dotenv

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from .users import get_user, update_last_login
from .passwords import verify_password


load_dotenv()

SECRET_KEY = os.getenv("SOVEREIGN_AI_JWT_SECRET")

if not SECRET_KEY:
    raise RuntimeError(
        "SOVEREIGN_AI_JWT_SECRET is not configured."
    )

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# OAuth2 token configuration
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Validate incoming Bearer JWT and verify active user status in MySQL.
    If the account was deleted, disabled, or rejected, access is immediately revoked.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        username = payload.get("sub")
        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = get_user(username)
    if user is None:
        raise credentials_exception

    # Verify user is not soft-deleted
    if user.get("deleted_at") is not None or user.get("status") == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled."
        )

    # Verify user status is APPROVED
    user_status = (user.get("status") or "").upper()
    if user_status == "DISABLED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled."
        )
    elif user_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account registration was rejected."
        )
    elif user_status == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is waiting for administrator approval."
        )
    elif user_status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: account not approved."
        )

    return user


def get_current_admin_user(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Backend RBAC guard: enforces that current user has admin role.
    Rejects operators, employees, or non-admins with HTTP 403 Forbidden.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrative privileges required."
        )
    return current_user


def authenticate_user(
    username: str,
    password: str
) -> Optional[Dict[str, Any]]:
    """
    Authenticate user credentials against MySQL.
    Checks existence, password hash, and account approval status.
    Raises HTTPException with specific error message if account is PENDING, REJECTED, or DISABLED.
    Returns user dict on success, None on invalid credentials.
    """
    user = get_user(username)
    if not user:
        return None

    if not verify_password(password, user["password"]):
        return None

    # Check soft-deletion
    if user.get("deleted_at") is not None or user.get("status") == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled."
        )

    # Check status requirements
    user_status = (user.get("status") or "").upper()
    if user_status == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is waiting for administrator approval."
        )
    elif user_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account registration was rejected."
        )
    elif user_status == "DISABLED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled."
        )
    elif user_status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not approved."
        )

    # Update last login timestamp in MySQL
    update_last_login(user["id"])
    return user