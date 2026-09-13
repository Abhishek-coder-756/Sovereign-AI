from passlib.context import CryptContext


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


ROLE_PASSWORD_PREFIXES = {
    "admin": "admin",
    "operator": "operator",
    "employee": "emp",
}


def validate_role_password(role: str, password: str) -> tuple[bool, str]:
    """
    Validate that password adheres to role-based prefix requirements
    and minimum length security standards.
    """
    if not role or role not in ROLE_PASSWORD_PREFIXES:
        return False, f"Invalid role '{role}'. Allowed roles: admin, operator, employee."

    required_prefix = ROLE_PASSWORD_PREFIXES[role]
    if not password or not password.startswith(required_prefix):
        return False, f"{role.capitalize()} passwords must start with '{required_prefix}'."

    min_length = max(8, len(required_prefix) + 3)
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long."

    return True, ""