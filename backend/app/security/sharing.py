from datetime import datetime, timedelta, timezone
from fastapi import HTTPException


# Store active shares
SHARES = {}


def create_share(
    owner: str,
    company: str,
    resource: str,
    shared_with: str,
    expiry_minutes: int
):
    # Check expiry
    if expiry_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="Expiry time must be greater than 0 minutes."
        )

    # Create unique share ID
    share_id = f"{owner}:{resource}:{shared_with}"

    # Calculate expiry time
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=expiry_minutes)
    )

    # Store share information
    SHARES[share_id] = {
        "owner": owner,
        "company": company,
        "resource": resource,
        "shared_with": shared_with,
        "expires_at": expires_at
    }

    return {
        "share_id": share_id,
        "resource": resource,
        "shared_with": shared_with,
        "expires_at": expires_at.isoformat()
    }


def check_share_access(
    share_id: str,
    username: str,
    company: str
):
    # Find share
    share = SHARES.get(share_id)

    if not share:
        raise HTTPException(
            status_code=404,
            detail="Share not found."
        )

    # Check user
    if share["shared_with"] != username:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this shared resource."
        )
    # Check company isolation
    if share["company"] != company:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company data isolation violation."
        )

    # Check expiry
    if datetime.now(timezone.utc) >= share["expires_at"]:
        raise HTTPException(
            status_code=403,
            detail="Shared access has expired."
        )

    return share