from bson import ObjectId
from mongoloader import your_turn
from fastapi import APIRouter, HTTPException, status, Request, Response
from ..models import NoteFolder, Note, Organization
from ..schemas import FolderCreate, NoteCreate
from .. import db
from . import functional_auth

router = APIRouter(prefix="/sample/v2")


def functional_post_folder(
    auth_result: HTTPException | Organization | None,
    folder: FolderCreate,
    parent: NoteFolder | None,
) -> NoteFolder:
    # No database access here
    if isinstance(auth_result, HTTPException):
        raise auth_result
    if auth_result is None:
        # admin gets a 422, other users don't get here, and already received a 403
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Organization does not exist",
        )

    if folder.parent_id:
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Parent folder does not exist",
            )
        if parent.organization_id != folder.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Parent and child organization mismatch",
            )
    return NoteFolder(
        name=folder.name,
        organization_id=str(auth_result.id),
        parent_id=None if parent is None else str(parent.id),
    )


@router.post("/folders/", status_code=201)
def post_folder(folder: FolderCreate, request: Request):
    auth_result = functional_auth.require_role_by_organization_id(
        folder.organization_id, request, functional_auth.Operation.WRITE
    )
    if folder.parent_id is None:
        org = (
            auth_result
            if isinstance(auth_result, HTTPException)
            else (
                db.get_organization(folder.organization_id)
                if (auth_result[1] is functional_auth.NoDatabaseAccessNeeded.SENTINEL)
                else auth_result[1]
            )
        )
    else:
        rr = your_turn(
            {
                "org": (
                    Organization,
                    Organization.id == ObjectId(folder.organization_id),
                ),
                "parent": (NoteFolder, NoteFolder.id == ObjectId(folder.parent_id)),
            }
        )
        org = rr["org"]
        parent = rr["parent"]

    doc = functional_post_folder(org, folder, parent)

    doc.insert()

    return Response(
        status_code=status.HTTP_201_CREATED,
        headers={"Location": f"/sample/v1/folders/{doc.id}"},
    )


@router.get("/folders/{folder_id}", response_model=NoteFolder)
def get_folder(folder_id: str, request: Request) -> NoteFolder:
    auth_result = functional_auth.require_role_by_folder_id(
        folder_id, request, functional_auth.Operation.READ
    )
    if isinstance(auth_result, HTTPException):
        raise auth_result

    folder = (
        db.get_note_folder(folder_id)
        if (auth_result[1] is functional_auth.NoDatabaseAccessNeeded.SENTINEL)
        else auth_result[1][-1]
    )

    if folder:
        return folder

    # admin gets a 404, other users don't get here, and already received a 403
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
    )


@router.post("/folders/{folder_id}/notes/", status_code=201)
def create_note(folder_id: str, note: NoteCreate, request: Request):
    auth_result = functional_auth.require_role_by_folder_id(
        folder_id, request, functional_auth.Operation.WRITE
    )
    if isinstance(auth_result, HTTPException):
        raise auth_result

    folder = (
        db.get_note_folder(folder_id)
        if auth_result[1] is functional_auth.NoDatabaseAccessNeeded.SENTINEL
        else auth_result[1][-1]
    )

    if not folder:
        # admin gets a 422, other users don't get here, and already received a 403
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Folder not found"
        )
    doc = db.create_note(
        folder,
        note.title,
        note.content,
        auth_result[0].email,
    )
    return Response(
        status_code=status.HTTP_201_CREATED,
        headers={"Location": f"/sample/v1/folders/{folder_id}/notes/{doc.id}"},
    )


@router.post("/notes/{note_id}/like", status_code=200, response_model=Note)
def like_note(note_id: str, request: Request):
    auth_result = functional_auth.require_role_by_note_id(
        note_id, request, functional_auth.Operation.WRITE
    )
    if isinstance(auth_result, HTTPException):
        raise auth_result

    note = db.like_note(note_id)
    if note:
        return note

    # admin gets a 404, other users don't get here, and already received a 403
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@router.get(
    "/folders/{folder_id}/notes/{note_id}", status_code=200, response_model=Note
)
def get_note(folder_id: str, note_id: str, request: Request):
    auth_result = functional_auth.require_role_by_note_id(
        note_id, request, functional_auth.Operation.READ
    )
    if isinstance(auth_result, HTTPException):
        raise auth_result

    note = (
        db.get_note(note_id)
        if auth_result[1] is functional_auth.NoDatabaseAccessNeeded.SENTINEL
        else auth_result[1][-1][-1]
    )
    if note and note.folder_id == folder_id:
        folder = (
            db.get_note_folder(folder_id)
            if auth_result[1] is functional_auth.NoDatabaseAccessNeeded.SENTINEL
            else auth_result[1][-1][0]
        )
        if folder:
            return note

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
