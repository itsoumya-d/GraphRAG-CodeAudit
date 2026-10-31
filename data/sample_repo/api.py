"""API layer that ties authentication, database, and files together."""
from auth import issue_token, verify_password
from db import find_user, save_user
from files import load_snapshot


def login(email: str, password: str):
    rows = find_user(email)
    if rows and verify_password(password, rows[0][1]):
        return {"token": issue_token(str(rows[0][0]))}
    return {"error": "invalid credentials"}


def restore_snapshot(path: str):
    return load_snapshot(path)


def register(email: str):
    save_user(email)
    return {"status": "created"}
