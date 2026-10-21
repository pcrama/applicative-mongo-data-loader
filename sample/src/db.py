from bson import ObjectId
from bunnet import UpdateResponse
from bunnet.operators import Inc
from .models import Organization, User, NoteFolder, Note


def get_organization(organization_id: str) -> Organization | None:
    return Organization.find_one(Organization.id == ObjectId(organization_id)).run()


def get_user(email: str) -> User | None:
    return User.find_one(User.email == email).run()


def get_note_folder(folder_id: str) -> NoteFolder | None:
    return NoteFolder.find_one(NoteFolder.id == ObjectId(folder_id)).run()


def get_note(note_id: str) -> Note | None:
    return Note.find_one(Note.id == ObjectId(note_id)).run()


def like_note(note_id: str | Note) -> Note | None:
    return (
        Note.find_one(Note.id == ObjectId(note_id))
        .update(Inc({Note.likes: 1}), response_type=UpdateResponse.NEW_DOCUMENT)
        .run()
    )


def create_note(
    folder: NoteFolder, title: str, content: str, creator_email: str
) -> Note:
    note = Note(
        title=title,
        content=content,
        creator_email=creator_email,
        folder_id=str(folder.id),
        likes=0,
    )
    note.insert()
    return note


def create_folder(
    name: str, organization: Organization, parent: NoteFolder | None = None
) -> NoteFolder:
    if parent and parent.organization_id != str(organization.id):
        raise ValueError("Parent folder must belong to the same organization")
    folder = NoteFolder(
        name=name,
        parent_id=str(parent.id) if parent else None,
        organization_id=str(organization.id),
    )
    folder.insert()
    return folder
