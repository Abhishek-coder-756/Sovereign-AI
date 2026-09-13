ROLE_PERMISSIONS = {
    "admin": {
        "read",
        "write",
        "execute",
        "manage_users",
        "admin_panel",
    },

    "operator": {
        "read",
        "write",
        "execute",
    },

    "employee": {
        "read",
        "execute",
    },
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())

    return permission in permissions


def is_admin(role: str) -> bool:
    return role == "admin"