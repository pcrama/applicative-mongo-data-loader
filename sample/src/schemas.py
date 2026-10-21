from pydantic import BaseModel
from typing import Optional


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    organization_id: str


class NoteCreate(BaseModel):
    title: str
    content: str
