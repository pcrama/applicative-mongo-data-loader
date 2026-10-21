from typing import Annotated, Optional
from bunnet import Document
from pydantic import BaseModel, Field


class Organization(Document):
    name: str


class User(Document):
    name: str
    email: Annotated[str, Field(description="login identifier")]
    roles: Annotated[
        list[str],
        Field(
            description="""Fine-grained access control. Each elemens is one of
    - 'admin' :: human with read/write rights on anything
    - 'viewer::<id>' :: read-access to all documents inside folders belonging to Organization with that id
    - 'editor::<id>' :: read/write-access to all documents inside folders belonging to Organization with that id""",
            default_factory=list,
        ),
    ]


class NoteFolder(Document):
    name: Annotated[
        str, Field(description="Name of the folder, does not need to be unique")
    ]
    parent_id: Annotated[
        Optional[str],
        Field(
            description="Notes can be placed arbitrarily deep in a nested tree structure"
        ),
    ]
    organization_id: Annotated[
        str,
        Field(
            description="""id of the Organization the NoteFolder belongs to.
    The invariant that a tree can belong to only one organization is maintained by the application, i.e.
    child_note_folder.organization_id == child_note_folder.parent.organization_id"""
        ),
    ]


class Note(Document):
    title: str
    content: str
    creator_email: Annotated[str, Field(description="Creator's email")]
    folder_id: Annotated[
        str,
        Field(
            description="Each note is inside a folder and belongs to the organization the folder belongs to"
        ),
    ]
    likes: Annotated[
        int,
        Field(
            description="Users can vote on notes via separate end-point, this field is not part of the POST"
        ),
        Field(default=0),
    ]
