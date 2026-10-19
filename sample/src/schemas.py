from pydantic import BaseModel, Field
from typing import Optional

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    organization_id: str

class FolderOut(BaseModel):
    id: str = Field(alias="_id")
    name: str
    organization_id: str
    parent_id: Optional[str] = None

class NoteCreate(BaseModel):
    title: str
    content: str
    folder_id: str

class NoteOut(BaseModel):
    id: str = Field(alias="_id")
    title: str
    content: str
    creator_email: str
    folder_id: str
    likes: int
