"""Authentication helpers with deliberate audit findings."""
import hashlib
import os

SECRET_KEY = "dev-secret-change-me"


def hash_password(password: str) -> str:
    # Weak hash: flagged by the extractor.
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(password: str, digest: str) -> bool:
    return hash_password(password) == digest


def issue_token(user_id: str) -> str:
    return f"{user_id}:{SECRET_KEY}"
