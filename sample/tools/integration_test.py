#!/usr/bin/env python3

from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from dataclasses import dataclass
import json
import os

from bunnet import init_bunnet
from bunnet.operators import And, Eq
from pymongo import MongoClient

from src.models import Organization, User, NoteFolder, Note
from src.settings import settings


def upsert_by(query, replacement):
    """Insert a document or replace the matching document."""
    existing = query.run()

    if existing is None:
        replacement.insert()
    else:
        replacement.id = existing.id
        replacement.replace()

    return replacement


@dataclass
class SampleDocuments:
    org_a: Organization
    org_b: Organization
    writer_a: User
    reader_ab: User
    admin: User
    folder_a: NoteFolder
    sub_folder_a: NoteFolder
    note_by_admin: Note
    note_a: Note
    folder_b: NoteFolder
    note_b: Note


def setup() -> SampleDocuments:
    mongo_uri = os.getenv(
        "MONGO_URI",
        f"mongodb://{settings.mongo_initdb_root_username}:{settings.mongo_initdb_root_password}@localhost:27017/?authSource=admin",
    )

    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")

        init_bunnet(
            database=client[settings.mongo_database],
            document_models=[Organization, User, NoteFolder, Note],
        )

        def make_user(email: str, name: str, roles: list[str]) -> User:
            return upsert_by(
                User.find_one(User.email == email),
                User(name=name, email=email, roles=roles),
            )

        def make_folder(
            name: str, parent: NoteFolder | None, organization: Organization
        ) -> NoteFolder:
            parent_id = None if parent is None else str(parent.id)
            org_id = str(organization.id)
            return upsert_by(
                NoteFolder.find_one(
                    And(
                        Eq(  # <- this makes the type checker happy but is less readable?
                            NoteFolder.name, name
                        ),
                        NoteFolder.parent_id == parent_id,  # ty: ignore[invalid-argument-type]
                        NoteFolder.organization_id == org_id,  # ty: ignore[invalid-argument-type]
                    )
                ),
                NoteFolder(name=name, parent_id=parent_id, organization_id=org_id),
            )

        def make_note(
            title: str, content: str, folder: NoteFolder, creator: User
        ) -> Note:
            folder_id = str(folder.id)
            return upsert_by(
                Note.find_one(And(Note.title == title, Note.folder_id == folder_id)),  # ty: ignore[invalid-argument-type]
                Note(
                    title=title,
                    content=content,
                    folder_id=folder_id,
                    creator_email=creator.email,
                    likes=0,
                ),
            )

        org_a = upsert_by(
            Organization.find_one(Organization.name == "a"),
            Organization(name="a"),
        )
        org_b = upsert_by(
            Organization.find_one(Organization.name == "b"),
            Organization(name="b"),
        )
        org_a_id = str(org_a.id)
        org_b_id = str(org_b.id)
        assert org_a_id != org_b_id, "Organization IDs should be different"

        writer_a = make_user(
            email="a@a.com", name="Writer A", roles=[f"editor::{org_a_id}"]
        )
        reader_ab = make_user(
            email="ab@a-and-b.com",
            name="Reader ab",
            roles=[f"viewer::{org_a_id}", f"viewer::{org_b_id}"],
        )
        admin = make_user(
            email="admin@example.com", name="Administrator", roles=["admin"]
        )
        assert len({str(o.id) for o in (writer_a, reader_ab, admin)}) == 3, (
            "All users should have unique IDs"
        )

        folder_a = make_folder(name="root 1 a", parent=None, organization=org_a)
        sub_folder_a = make_folder(
            name="sub-root inside a root folder for a",
            parent=folder_a,
            organization=org_a,
        )
        assert str(folder_a.id) != str(sub_folder_a.id), (
            "Folder IDs should be different"
        )

        folder_b = make_folder(name="root b", parent=None, organization=org_b)
        return SampleDocuments(
            org_a=org_a,
            org_b=org_b,
            writer_a=writer_a,
            reader_ab=reader_ab,
            admin=admin,
            folder_a=folder_a,
            sub_folder_a=sub_folder_a,
            note_by_admin=make_note(
                title="Note by admin",
                content="This is a note from your friendly administrator",
                folder=folder_a,
                creator=admin,
            ),
            note_a=make_note(
                title="Note in sub folder",
                content="This is a note in a sub-folder",
                folder=sub_folder_a,
                creator=writer_a,
            ),
            folder_b=folder_b,
            note_b=make_note(
                title="Note in folder b",
                content="This is a note in folder b",
                folder=folder_b,
                creator=admin,
            ),
        )


NONEXISTENT_NOTE_ID = "000000000000000000000000"
NONEXISTENT_FOLDER_ID = "111111111111111111111111"


def client_create_folder(
    base_url: str,
    user: User | None,
    org: Organization | str,
    name: str,
    parent: NoteFolder | str | None,
) -> Note:
    parent_id = str(parent.id) if isinstance(parent, NoteFolder) else parent
    organization_id = str(org.id) if isinstance(org, Organization) else org
    resp = urlopen(
        Request(
            urljoin(base_url + "/", "folders/"),
            data=json.dumps(
                {
                    "name": name,
                    "parent_id": parent_id,
                    "organization_id": organization_id,
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({} if user is None else {"X-User": user.email}),
            },
        )
    )
    location = resp.headers.get("Location")
    if not location:
        raise ValueError("No Location header in response")
    folder_id = location.split("/")[-1]
    return client_get_folder(base_url, user, folder_id)


def client_get_folder(
    base_url: str, user: User | None, folder: NoteFolder | str
) -> NoteFolder:
    folder_id = str(folder.id) if isinstance(folder, NoteFolder) else folder
    resp = urlopen(
        Request(
            urljoin(base_url + "/", f"folders/{folder_id}"),
            headers={} if user is None else {"X-User": user.email},
        )
    )
    return NoteFolder.model_validate_json(resp.read())


def client_create_note(
    base_url: str, user: User | None, folder: NoteFolder | str, title: str, content: str
) -> Note:
    folder_id = folder if isinstance(folder, str) else str(folder.id)
    resp = urlopen(
        Request(
            urljoin(base_url + "/", f"folders/{folder_id}/notes/"),
            data=f'{{"title": "{title}", "content": "{content}"}}'.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({} if user is None else {"X-User": user.email}),
            },
        )
    )
    location = resp.headers.get("Location")
    if not location:
        raise ValueError("No Location header in response")
    note_id = location.split("/")[-1]
    return client_get_note(base_url, user, (folder_id, note_id))


def client_get_note(
    base_url: str, user: User | None, note: Note | tuple[str, str]
) -> Note:
    folder_id, note_id = (
        note if isinstance(note, tuple) else (note.folder_id, str(note.id))
    )
    resp = urlopen(
        Request(
            urljoin(base_url + "/", f"folders/{folder_id}/notes/{note_id}"),
            headers={} if user is None else {"X-User": user.email},
        )
    )
    return Note.model_validate_json(resp.read())


def client_like_note(base_url: str, user: User | None, note: Note | str) -> Note:
    note_id = note if isinstance(note, str) else str(note.id)
    resp = urlopen(
        Request(
            urljoin(base_url + "/", f"notes/{note_id}/like"),
            data={},
            headers={} if user is None else {"X-User": user.email},
        )
    )
    return Note.model_validate_json(resp.read())


def test_can_create_folder(base_url: str, sample_docs: SampleDocuments) -> None:
    new_folder = client_create_folder(
        base_url,
        sample_docs.admin,
        sample_docs.org_a,
        "New Folder",
        sample_docs.folder_a,
    )
    assert new_folder.name == "New Folder"
    assert new_folder.parent_id == str(sample_docs.folder_a.id)
    assert new_folder.organization_id == str(sample_docs.org_a.id)

    new_sub_folder = client_create_folder(
        base_url, sample_docs.writer_a, sample_docs.org_a, "New Sub Folder", new_folder
    )
    assert new_sub_folder.name == "New Sub Folder"
    assert new_sub_folder.parent_id == str(new_folder.id)
    assert new_sub_folder.organization_id == str(sample_docs.org_a.id)

    for user, parent, org in (
        (sample_docs.writer_a, sample_docs.folder_b, sample_docs.org_b),
        (sample_docs.writer_a, sample_docs.folder_b, sample_docs.org_a),
        (sample_docs.admin, sample_docs.folder_b, sample_docs.org_a),
        (sample_docs.reader_ab, sample_docs.sub_folder_a, sample_docs.org_a),
    ):
        try:
            client_create_folder(base_url, user, org, "New Folder Name", parent)
        except HTTPError as e:
            assert e.code == (422 if parent.organization_id != str(org.id) else 403)
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to create folder for {org=} inside {parent=}, but got no error."
            )

    for user in (sample_docs.writer_a, sample_docs.admin):
        try:
            client_create_folder(
                base_url,
                user,
                sample_docs.org_a,
                "New Folder Name",
                NONEXISTENT_FOLDER_ID,
            )
        except HTTPError as e:
            assert e.code == 422
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to create folder inside non-existent parent, but got no error."
            )

    try:
        client_create_folder(
            base_url, None, sample_docs.org_a, "New Folder Name", sample_docs.folder_a
        )
    except HTTPError as e:
        assert e.code == 401
    else:
        raise AssertionError(
            "Expected HTTPError for anonymous user trying to create folder, but got no error."
        )


def test_can_get_folder(base_url: str, sample_docs: SampleDocuments) -> None:
    for user, expected_folder in (
        (sample_docs.writer_a, sample_docs.folder_a),
        (sample_docs.reader_ab, sample_docs.sub_folder_a),
        (sample_docs.reader_ab, sample_docs.folder_b),
        (sample_docs.admin, sample_docs.folder_b),
    ):
        folder = client_get_folder(base_url, user, expected_folder)
        assert folder.name == expected_folder.name
        assert folder.parent_id == expected_folder.parent_id
        assert folder.organization_id == str(expected_folder.organization_id)

    try:
        client_get_folder(base_url, None, sample_docs.folder_a)
    except HTTPError as e:
        assert e.code == 401
    else:
        raise AssertionError(
            "Expected HTTPError for anonymous user trying to access folder_a, but got no error."
        )

    try:
        client_get_folder(base_url, sample_docs.writer_a, sample_docs.folder_b)
    except HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError(
            "Expected HTTPError for writer_a trying to access folder_b, but got no error."
        )

    for user in [sample_docs.writer_a, sample_docs.reader_ab, sample_docs.admin]:
        try:
            client_get_folder(base_url, user, NONEXISTENT_FOLDER_ID)
        except HTTPError as e:
            assert e.code == (404 if user == sample_docs.admin else 403)
        else:
            raise AssertionError(
                f"Expected HTTPError for {user=} trying to access non-existent folder, but got no error."
            )


def test_can_read(base_url: str, sample_docs: SampleDocuments) -> None:
    for user in [sample_docs.writer_a, sample_docs.reader_ab, sample_docs.admin]:
        doc = client_get_note(base_url, user, sample_docs.note_a)
        assert doc.title == sample_docs.note_a.title
        assert doc.content == sample_docs.note_a.content

    try:
        client_get_note(base_url, None, sample_docs.note_a)
    except HTTPError as e:
        assert e.code == 401
    else:
        raise AssertionError(
            "Expected HTTPError for anonymous trying to access note_a, but got no error."
        )

    for user in [sample_docs.reader_ab, sample_docs.admin]:
        doc = client_get_note(base_url, user, sample_docs.note_b)
        assert doc.title == sample_docs.note_b.title
        assert doc.content == sample_docs.note_b.content

    try:
        client_get_note(base_url, sample_docs.writer_a, sample_docs.note_b)
    except HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError(
            "Expected HTTPError for writer_a trying to access note_b, but got no error."
        )

    for user in [sample_docs.writer_a, sample_docs.reader_ab, sample_docs.admin]:
        try:
            client_get_note(
                base_url, user, (sample_docs.note_a.folder_id, NONEXISTENT_NOTE_ID)
            )
        except HTTPError as e:
            if user == sample_docs.admin:
                assert e.code == 404  # admin gets a 404 for non-existent note
            else:
                assert (
                    e.code == 403
                )  # note doesn't exist -> can't check folder for organization
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to access non-existent note in existing folder, but got no error."
            )

        try:
            client_get_note(
                base_url, user, (NONEXISTENT_FOLDER_ID, str(sample_docs.note_a.id))
            )
        except HTTPError as e:
            assert e.code == 404  # note exists -> can check folder for organization
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to access non-existent note in existing folder, but got no error."
            )

    try:
        client_get_note(
            base_url,
            sample_docs.writer_a,
            (str(sample_docs.folder_a.id), str(sample_docs.note_b.id)),
        )
    except HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError(
            "Expected HTTPError for writer_a trying to access note_b, but got no error."
        )

    try:
        client_get_note(
            base_url,
            sample_docs.writer_a,
            (str(sample_docs.folder_a.id), str(sample_docs.note_a.id)),
        )
    except HTTPError as e:
        assert e.code == 404
    else:
        raise AssertionError(
            "Expected HTTPError for writer_a trying to access note_a from bad folder, but got no error."
        )


def test_can_like(base_url: str, sample_docs: SampleDocuments) -> None:
    doc = client_get_note(base_url, sample_docs.admin, sample_docs.note_a)
    expected_liked = doc.likes + 1

    for user in [sample_docs.writer_a, sample_docs.admin]:
        new_doc = client_like_note(base_url, user, doc)
        assert new_doc.likes == expected_liked
        expected_liked += 1

    try:
        client_like_note(base_url, sample_docs.reader_ab, sample_docs.note_a)
    except HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError(
            "Expected HTTPError for reader_ab trying to like note_a, but got no error."
        )

    try:
        client_like_note(base_url, None, sample_docs.note_a)
    except HTTPError as e:
        assert e.code == 401
    else:
        raise AssertionError(
            "Expected HTTPError for anonymous user trying to like note_a, but got no error."
        )

    doc = client_get_note(base_url, user, sample_docs.note_b)
    expected_liked = doc.likes + 1
    new_doc = client_like_note(base_url, sample_docs.admin, doc)
    assert new_doc.likes == expected_liked

    try:
        client_like_note(base_url, sample_docs.writer_a, doc)
    except HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError(
            "Expected HTTPError for writer_a trying to access note_b, but got no error."
        )

    for user in [sample_docs.writer_a, sample_docs.reader_ab, sample_docs.admin]:
        try:
            client_like_note(base_url, user, NONEXISTENT_NOTE_ID)
        except HTTPError as e:
            if user == sample_docs.admin:
                assert e.code == 404  # admin gets a 404 for non-existent note
            else:
                assert (
                    e.code == 403
                )  # note doesn't exist -> can't check folder for organization
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to access non-existent note in existing folder, but got no error."
            )


def test_can_create_note(base_url: str, sample_docs: SampleDocuments) -> None:
    doc = client_create_note(
        base_url,
        sample_docs.writer_a,
        sample_docs.sub_folder_a,
        "New Note Title",
        "New Note Content",
    )
    assert doc.title == "New Note Title"
    assert doc.content == "New Note Content"
    assert doc.creator_email == sample_docs.writer_a.email
    assert doc.likes == 0
    for user in [sample_docs.writer_a, sample_docs.reader_ab, sample_docs.admin]:
        try:
            client_create_note(
                base_url,
                user,
                NONEXISTENT_FOLDER_ID,
                "New Note Title",
                "New Note Content",
            )
        except HTTPError as e:
            if user == sample_docs.admin:
                assert e.code == 422  # 422: body refers to invalid folder
            elif user in (sample_docs.reader_ab, sample_docs.writer_a):
                assert e.code == 403  # no folder -> can't check folder for organization
            else:
                assert False, f"Not reached, {user=}"  # should not happen
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to create note in  non-existent folder, but got no error."
            )
    for user, folder in (
        (sample_docs.writer_a, sample_docs.folder_b),
        (sample_docs.reader_ab, sample_docs.sub_folder_a),
    ):
        try:
            client_create_note(
                base_url, user, folder, "New Note Title", "New Note Content"
            )
        except HTTPError as e:
            assert e.code == 403
        else:
            raise AssertionError(
                f"Expected HTTPError for {user.email} trying to create note in {folder=}, but got no error."
            )


def test_all(base_url: str, sample_docs: SampleDocuments) -> None:
    test_can_read(base_url, sample_docs)
    test_can_like(base_url, sample_docs)
    test_can_create_note(base_url, sample_docs)
    test_can_create_folder(base_url, sample_docs)
    test_can_get_folder(base_url, sample_docs)


if __name__ == "__main__":
    sample_docs = setup()
    test_all("http://localhost:8000/sample/v1/", sample_docs)
