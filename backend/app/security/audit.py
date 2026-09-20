from datetime import datetime, timezone
from pathlib import Path


AUDIT_FILE = Path("data/audit.log")


def log_event(
    username: str,
    company: str,
    action: str,
    status: str,
    details: str = ""
):
    """
    Record an important system action in the local audit log.
    """

    AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    log_entry = (
        f"{timestamp} | "
        f"user={username} | "
        f"company={company} | "
        f"action={action} | "
        f"status={status} | "
        f"details={details}\n"
    )

    with AUDIT_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:
        file.write(log_entry)