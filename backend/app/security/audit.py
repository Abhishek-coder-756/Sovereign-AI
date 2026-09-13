from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from db import get_connection

AUDIT_FILE = Path("data/audit.log")

# Cache company name to id
_COMPANY_CACHE = {}


def _resolve_company_id(company_name: str) -> Optional[int]:
    if not company_name:
        return None
    if company_name in _COMPANY_CACHE:
        return _COMPANY_CACHE[company_name]

    connection = get_connection()
    if not connection:
        return None
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM companies WHERE name = %s", (company_name,))
        row = cursor.fetchone()
        if row:
            _COMPANY_CACHE[company_name] = row["id"]
            return row["id"]
    except Exception:
        pass
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
    return None


def log_event(
    username: str,
    company: str,
    action: str,
    status: str,
    details: str = "",
    user_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    target_role: Optional[str] = None,
    company_id: Optional[int] = None,
):
    """
    Record an important system action in both MySQL audit_logs table
    and the local data/audit.log file.
    Never logs passwords or hashes.
    """
    # Resolve company ID if not supplied
    if company_id is None and company:
        company_id = _resolve_company_id(company)

    # 1. Log to MySQL audit_logs table
    connection = get_connection()
    if connection:
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO audit_logs (
                    username, user_id, company_id, action, status,
                    target_user_id, target_username, target_role, details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    username,
                    user_id,
                    company_id,
                    action,
                    status,
                    target_user_id,
                    target_username,
                    target_role,
                    details
                )
            )
            connection.commit()
        except Exception as e:
            print(f"MySQL audit log write error: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection.is_connected():
                connection.close()

    # 2. Append to local audit.log file (for backward compatibility)
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        target_info = f" | target={target_username}" if target_username else ""
        log_entry = (
            f"{timestamp} | "
            f"user={username} | "
            f"company={company} | "
            f"action={action} | "
            f"status={status}{target_info} | "
            f"details={details}\n"
        )
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"File audit log write error: {e}")