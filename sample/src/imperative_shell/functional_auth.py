from collections.abc import Callable
from enum import Enum, StrEnum
from typing import Literal

from fastapi import HTTPException, status, Request
from ..models import User, Organization, NoteFolder, Note
from .. import db


class NoDatabaseAccessNeeded(Enum):
    SENTINEL = object()


class Operation(StrEnum):
    READ = "READ"
    WRITE = "WRITE"


# Dummy authentication for demonstration
def get_current_user(request: Request) -> User | HTTPException:
    # In real app, extract user from request/session/token
    user_id = request.headers.get("X-User")
    if user_id and (user := db.get_user(user_id)):
        return user
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
    )


def require_role[T](
    get_org: Callable[[T], Organization | None],
    get_obj: Callable[[], T | None],
    request: Request,
    op: Operation,
) -> (
    tuple[User, tuple[Organization, T] | Literal[NoDatabaseAccessNeeded.SENTINEL]]
    | HTTPException
):
    current_user = get_current_user(request)
    if isinstance(current_user, HTTPException):
        raise current_user
    roles = current_user.roles
    if "admin" in roles:
        return current_user, NoDatabaseAccessNeeded.SENTINEL
    obj = get_obj()
    org = None if obj is None else get_org(obj)
    if obj is None or org is None:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Organization ID not found"
        )
    org_id = str(org.id)
    if f"editor::{org_id}" in roles:
        return (current_user, (org, obj))
    if op == Operation.READ and f"viewer::{org_id}" in roles:
        return (current_user, (org, obj))
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to {op.value}"
    )


def require_role_by_organization_id(
    org_id: str, request: Request, op: Operation
) -> (
    tuple[User, Organization | Literal[NoDatabaseAccessNeeded.SENTINEL]] | HTTPException
):
    result = require_role(
        lambda org: org, lambda: db.get_organization(org_id), request, op
    )
    if isinstance(result, tuple):
        return (
            result[0],
            result[1] if result[1] is NoDatabaseAccessNeeded.SENTINEL else result[1][0],
        )
    else:
        return result


def require_role_by_folder_id(
    folder_id: str, request: Request, op: Operation
) -> (
    tuple[
        User, tuple[Organization, NoteFolder] | Literal[NoDatabaseAccessNeeded.SENTINEL]
    ]
    | HTTPException
):
    return require_role(
        lambda folder: db.get_organization(folder.organization_id),
        lambda: db.get_note_folder(folder_id),
        request,
        op,
    )


def require_role_by_note_id(
    note_id: str, request: Request, op: Operation
) -> (
    tuple[
        User,
        tuple[Organization, tuple[NoteFolder, Note]]
        | Literal[NoDatabaseAccessNeeded.SENTINEL],
    ]
    | HTTPException
):
    def get_folder_and_note() -> tuple[NoteFolder, Note] | None:
        note = db.get_note(note_id)
        if note is None:
            return None
        folder = db.get_note_folder(note.folder_id)
        if folder is None:
            return None
        return (folder, note)

    def get_organization(
        folder_and_note: tuple[NoteFolder, Note],
    ) -> Organization | None:
        return db.get_organization(folder_and_note[0].organization_id)

    return require_role(get_organization, get_folder_and_note, request, op)
