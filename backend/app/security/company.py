from fastapi import HTTPException


def check_company_access(
    user_company: str,
    resource_company: str
):
    if user_company != resource_company:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company data isolation violation."
        )

    return True

