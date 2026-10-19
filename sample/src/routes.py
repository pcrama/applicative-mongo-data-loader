from fastapi import APIRouter, Depends, HTTPException, status, Request
from sample.src.models import Organization, User, NoteFolder, Note
from sample.src.schemas import FolderCreate, FolderOut, NoteCreate, NoteOut
from sample.src.auth import get_current_user, require_role

router = APIRouter(prefix="/sample/v1")

@router.post("/folders/", status_code=201)
async def create_folder(folder: FolderCreate, user: User = Depends(get_current_user)):
    # Check org exists
    org = Organization.find_one(Organization.id == folder.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization does not exist")
    if not require_role(folder.organization_id, user.roles, write=True):
        raise HTTPException(status_code=403, detail="No write rights to organization")
    if folder.parent_id:
        parent = NoteFolder.find_one(NoteFolder.id == folder.parent_id)
        if not parent:
            raise HTTPException(status_code=422, detail="Parent folder does not exist")
        if parent.organization_id != folder.organization_id:
            raise HTTPException(status_code=422, detail="Parent and child organization mismatch")
    doc = NoteFolder.model_validate(folder.model_dump())
    doc.insert()
    return {"location": f"/sample/v1/folders/{doc.id}"}

@router.get("/folders/{id}", response_model=FolderOut)
async def get_folder(id: str, user: User = Depends(get_current_user)):
    folder = NoteFolder.find_one(NoteFolder.id == id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    org = Organization.find_one(Organization.id == folder.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization does not exist")
    if not require_role(folder.organization_id, user.roles, write=False):
        raise HTTPException(status_code=403, detail="No read rights to organization")
    return folder

@router.post("/folders/{folder_id}/notes/", status_code=201)
async def create_note(folder_id: str, note: NoteCreate, user: User = Depends(get_current_user)):
    folder = NoteFolder.find_one(NoteFolder.id == folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    org = Organization.find_one(Organization.id == folder.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization does not exist")
    if not require_role(folder.organization_id, user.roles, write=True):
        raise HTTPException(status_code=403, detail="No write rights to organization")
    doc = Note.model_validate(note.model_dump() | {"creator_email": user.email})
    doc.insert()
    return {"location": f"/sample/v1/folders/{folder_id}/notes/{doc.id}"}
