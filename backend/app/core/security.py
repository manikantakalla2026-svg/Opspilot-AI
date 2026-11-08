import hashlib
import secrets

from fastapi import Header, HTTPException

from app.core.config import settings


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def require_workspace(x_workspace_token: str = Header(default="")):
    if not settings.workspace_token:
        raise HTTPException(503, "Workspace access is not configured")
    if not secrets.compare_digest(x_workspace_token, settings.workspace_token.get_secret_value()):
        raise HTTPException(401, "Invalid workspace token")
