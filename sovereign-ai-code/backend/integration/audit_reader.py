from typing import List, Dict, Any, Optional
from db import get_connection


def list_events(
    company: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Retrieve audit events from MySQL audit_logs table, ordered newest first.
    Filters by company for company data isolation.
    Excludes any sensitive data.
    """
    connection = get_connection()
    if not connection:
        return []

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                a.id,
                a.username,
                a.user_id,
                a.company_id,
                COALESCE(c.name, '') AS company,
                a.action,
                a.status,
                a.target_user_id,
                a.target_username,
                a.target_role,
                a.details,
                a.created_at,
                COALESCE(u.role, '') AS user_role
            FROM audit_logs a
            LEFT JOIN companies c ON a.company_id = c.id
            LEFT JOIN users u ON (a.user_id = u.id OR a.username = u.username)
        """
        params = []

        if company:
            query += " WHERE c.name = %s OR (a.company_id IS NULL AND a.details LIKE %s)"
            params.append(company)
            params.append(f"%{company}%")

        query += " ORDER BY a.created_at DESC, a.id DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        events = []
        for r in rows:
            events.append({
                "id": r["id"],
                "timestamp": r["created_at"].isoformat() if r.get("created_at") else "",
                "user": r["username"] or "system",
                "role": r["user_role"] or "",
                "company": r["company"] or (company or ""),
                "action": r["action"],
                "status": r["status"] or "",
                "target": r["target_username"] or (str(r["target_user_id"]) if r["target_user_id"] else ""),
                "target_role": r["target_role"] or "",
                "details": r["details"] or "",
            })

        return events

    except Exception as e:
        print(f"MySQL audit reader error: {e}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()