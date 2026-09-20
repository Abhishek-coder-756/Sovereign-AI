ROLE_PERMISSIONS = {
    "admin": {
        "read",
        "write",
        "execute",
        "manage_users"
    },

    "operator": {
        "read",
        "execute"
    }
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())

    return permission in permissions