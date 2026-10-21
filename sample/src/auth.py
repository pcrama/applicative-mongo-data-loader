from collections.abc import Callable
from enum import StrEnum
from fastapi import HTTPException, status, Request
from .models import User
from . import db


class Operation(StrEnum):
    READ = "READ"
    WRITE = "WRITE"


# Dummy authentication for demonstration
def get_current_user(request: Request) -> User:
    # In real app, extract user from request/session/token
    user_id = request.headers.get("X-User")
    if user_id and (user := db.get_user(user_id)):
        return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
    )


def require_role[T](
    get_org: Callable[[T], str | None], obj: T, request: Request, op: Operation
) -> None:
    roles = get_current_user(request).roles
    if "admin" in roles:
        return
    org_id = get_org(obj)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Organization ID not found"
        )
    if f"editor::{org_id}" in roles:
        return
    if op == Operation.READ and f"viewer::{org_id}" in roles:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to {op.value}"
    )


def require_role_by_organization_id(
    org_id: str, request: Request, op: Operation
) -> None:
    require_role(
        lambda oid: org_id if db.get_organization(oid) else None, org_id, request, op
    )


def require_role_by_folder_id(folder_id: str, request: Request, op: Operation) -> None:
    require_role(
        lambda fid: (
            (
                folder.organization_id
                if db.get_organization(folder.organization_id)
                else None
            )
            if (folder := db.get_note_folder(fid))
            else None
        ),
        folder_id,
        request,
        op,
    )


def require_role_by_note_id(note_id: str, request: Request, op: Operation) -> None:
    require_role(
        lambda nid: (
            (
                folder.organization_id
                if db.get_organization(folder.organization_id)
                else None
            )
            if (
                folder := (
                    db.get_note_folder(note.folder_id)
                    if (note := db.get_note(nid))
                    else None
                )
            )
            else None
        ),
        note_id,
        request,
        op,
    )
