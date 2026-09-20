from .passwords import hash_password


USERS = {
    "admin": {
        "username": "admin",
        "password": hash_password("admin123"),
        "role": "admin",
        "company": "MRPL"
    },

    "operator": {
        "username": "operator",
        "password": hash_password("operator123"),
        "role": "operator",
        "company": "MRPL"
    },
    "other_user": {
        "username": "other_user",
        "password": hash_password("other123"),
        "role": "admin",
        "company": "OTHER_COMPANY"
    }
}


def get_user(username: str):
    return USERS.get(username)