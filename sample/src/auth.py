from fastapi import Depends, HTTPException, status, Request
from sample.src.models import User
from typing import Optional

# Dummy authentication for demonstration
async def get_current_user(request: Request) -> User:
    # In real app, extract user from request/session/token
    user = request.headers.get("X-User")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # Simulate user lookup
    # Replace with real DB lookup
    return User(name=user, email=user, roles=["admin"])  # Always admin for now

def require_role(org_id: str, roles: list[str], write: bool = False):
    if "admin" in roles:
        return True
    if write:
        return f"editor::{org_id}" in roles
    return f"viewer::{org_id}" in roles or f"editor::{org_id}" in roles
