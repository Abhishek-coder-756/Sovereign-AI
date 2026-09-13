from typing import Optional, List, Dict, Any
from db import get_connection
from .passwords import hash_password


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user information from MySQL by username.
    Includes status, role, company, timestamps.
    """
    connection = get_connection()
    if not connection:
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.name,
                u.mobile,
                u.password,
                u.role,
                u.company_id,
                c.name AS company,
                u.status,
                u.created_at,
                u.updated_at,
                u.approved_at,
                u.approved_by,
                u.deleted_at,
                u.deleted_by,
                u.last_login_at
            FROM users u
            JOIN companies c
                ON u.company_id = c.id
            WHERE u.username = %s
            """,
            (username,)
        )
        return cursor.fetchone()

    except Exception as e:
        print(f"MySQL user lookup error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch user information from MySQL by user id.
    """
    connection = get_connection()
    if not connection:
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.name,
                u.mobile,
                u.password,
                u.role,
                u.company_id,
                c.name AS company,
                u.status,
                u.created_at,
                u.updated_at,
                u.approved_at,
                u.approved_by,
                u.deleted_at,
                u.deleted_by,
                u.last_login_at
            FROM users u
            JOIN companies c
                ON u.company_id = c.id
            WHERE u.id = %s
            """,
            (user_id,)
        )
        return cursor.fetchone()

    except Exception as e:
        print(f"MySQL user lookup by ID error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def create_user(
    username: str,
    name: str,
    mobile: str,
    role: str,
    company_id: int,
    hashed_password: str,
    status: str = "PENDING"
) -> Optional[int]:
    """
    Insert a new user record.
    Returns the newly generated user ID on success, or None on failure.
    """
    connection = get_connection()
    if not connection:
        return None

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (
                username, name, mobile, role, company_id, password, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (username, name, mobile, role, company_id, hashed_password, status)
        )
        connection.commit()
        return cursor.lastrowid

    except Exception as e:
        print(f"MySQL create user error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def update_user_status(
    user_id: int,
    status: str,
    actor_username: str
) -> bool:
    """
    Update status of a user (e.g. APPROVED, REJECTED, DISABLED).
    If status is APPROVED, records approved_at and approved_by.
    """
    connection = get_connection()
    if not connection:
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        if status == "APPROVED":
            cursor.execute(
                """
                UPDATE users
                SET status = %s, approved_at = NOW(), approved_by = %s
                WHERE id = %s
                """,
                (status, actor_username, user_id)
            )
        else:
            cursor.execute(
                """
                UPDATE users
                SET status = %s
                WHERE id = %s
                """,
                (status, user_id)
            )
        connection.commit()
        return cursor.rowcount > 0

    except Exception as e:
        print(f"MySQL update user status error: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def soft_delete_user(
    user_id: int,
    actor_username: str
) -> bool:
    """
    Perform safe soft-deletion of a user. Sets deleted_at and deleted_by.
    """
    connection = get_connection()
    if not connection:
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE users
            SET status = 'DELETED', deleted_at = NOW(), deleted_by = %s
            WHERE id = %s
            """,
            (actor_username, user_id)
        )
        connection.commit()
        return cursor.rowcount > 0

    except Exception as e:
        print(f"MySQL soft delete user error: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def update_last_login(user_id: int) -> bool:
    """
    Record last successful login timestamp.
    """
    connection = get_connection()
    if not connection:
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = %s",
            (user_id,)
        )
        connection.commit()
        return True

    except Exception as e:
        print(f"MySQL update last login error: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def count_active_admins(company_id: int) -> int:
    """
    Count active, approved, non-deleted administrators for a company.
    Guards against removing or disabling the last active admin.
    """
    connection = get_connection()
    if not connection:
        return 0

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE company_id = %s
              AND role = 'admin'
              AND status = 'APPROVED'
              AND deleted_at IS NULL
            """,
            (company_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    except Exception as e:
        print(f"MySQL count active admins error: {e}")
        return 0

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def list_company_users(
    company_id: int,
    status: Optional[str] = None,
    include_deleted: bool = False
) -> List[Dict[str, Any]]:
    """
    List users belonging to a company. Excludes password hashes.
    """
    connection = get_connection()
    if not connection:
        return []

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT
                u.id,
                u.username,
                u.name,
                u.mobile,
                u.role,
                u.company_id,
                c.name AS company,
                u.status,
                u.created_at,
                u.updated_at,
                u.approved_at,
                u.approved_by,
                u.deleted_at,
                u.deleted_by,
                u.last_login_at
            FROM users u
            JOIN companies c
                ON u.company_id = c.id
            WHERE u.company_id = %s
        """
        params = [company_id]

        if not include_deleted:
            query += " AND u.deleted_at IS NULL AND u.status != 'DELETED'"

        if status:
            query += " AND u.status = %s"
            params.append(status)

        query += " ORDER BY u.created_at DESC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        # Convert datetimes to isoformat strings for clean API consumption
        for row in rows:
            for k in ("created_at", "updated_at", "approved_at", "deleted_at", "last_login_at"):
                if row.get(k):
                    row[k] = row[k].isoformat()
        return rows

    except Exception as e:
        print(f"MySQL list company users error: {e}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_company_user_stats(company_id: int) -> Dict[str, int]:
    """
    Aggregate statistics for company dashboard:
    Total, Pending, Approved, Active, Disabled, Employees, Operators, Admins.
    """
    connection = get_connection()
    stats = {
        "total_users": 0,
        "pending": 0,
        "approved": 0,
        "active": 0,
        "disabled": 0,
        "employees": 0,
        "operators": 0,
        "admins": 0,
    }
    if not connection:
        return stats

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END) AS active_total,
                SUM(CASE WHEN status = 'PENDING' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS pending_count,
                SUM(CASE WHEN status = 'APPROVED' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS approved_count,
                SUM(CASE WHEN status = 'APPROVED' AND deleted_at IS NULL AND last_login_at IS NOT NULL THEN 1 ELSE 0 END) AS logged_in_count,
                SUM(CASE WHEN status = 'DISABLED' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS disabled_count,
                SUM(CASE WHEN role = 'employee' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS employee_count,
                SUM(CASE WHEN role = 'operator' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS operator_count,
                SUM(CASE WHEN role = 'admin' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS admin_count
            FROM users
            WHERE company_id = %s
            """,
            (company_id,)
        )
        row = cursor.fetchone()
        if row:
            stats["total_users"] = int(row["active_total"] or 0)
            stats["pending"] = int(row["pending_count"] or 0)
            stats["approved"] = int(row["approved_count"] or 0)
            stats["active"] = int(row["approved_count"] or 0)
            stats["disabled"] = int(row["disabled_count"] or 0)
            stats["employees"] = int(row["employee_count"] or 0)
            stats["operators"] = int(row["operator_count"] or 0)
            stats["admins"] = int(row["admin_count"] or 0)

        return stats

    except Exception as e:
        print(f"MySQL get user stats error: {e}")
        return stats

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_company_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch company record by company name.
    """
    connection = get_connection()
    if not connection:
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, created_at FROM companies WHERE name = %s", (name,))
        return cursor.fetchone()

    except Exception as e:
        print(f"MySQL get company error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_all_companies() -> List[Dict[str, Any]]:
    """
    List all available companies.
    """
    connection = get_connection()
    if not connection:
        return []

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM companies ORDER BY id")
        return cursor.fetchall()

    except Exception as e:
        print(f"MySQL get all companies error: {e}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()