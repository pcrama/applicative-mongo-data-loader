#!/usr/bin/env python3

import os
from typing import Annotated

from bunnet import Document, init_bunnet
from bunnet.operators import And
from pydantic import Field
from pymongo import MongoClient


class Organization(Document):
    name: str


class User(Document):
    name: str
    email: Annotated[str, Field(description="Login identifier")]
    roles: Annotated[
        list[str],
        Field(default_factory=list, description="Fine-grained access-control roles"),
    ]


class NoteFolder(Document):
    name: Annotated[str, Field(description="Folder name")]
    parent_id: Annotated[str | None, Field(description="Parent folder ID")]
    organization_id: Annotated[str, Field(description="Owning organization ID")]


class Note(Document):
    title: str
    content: str
    creator_email: Annotated[str, Field(description="Creator's email")]
    folder_id: Annotated[str, Field(description="Containing folder ID")]
    likes: Annotated[int, Field(default=0)]


def upsert_by(query, replacement):
    """Insert a document or replace the matching document."""
    existing = query.run()

    if existing is not None:
        replacement.id = existing.id
        replacement.replace()
    else:
        replacement.insert()

    return replacement


def main():
    mongo_uri = os.getenv(
        "MONGO_URI",
        "mongodb://root:Test1234@localhost:27017/?authSource=admin",
    )
    database_name = os.getenv("MONGO_DATABASE", "notes_test")

    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")

        init_bunnet(
            database=client[database_name],
            document_models=[Organization, User, NoteFolder, Note],
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
        print(f"Organization A ID: {org_a_id}")
        print(f"Organization B ID: {org_b_id}")

        upsert_by(
            User.find_one(User.email == "a@a.com"),
            User(
                name="Writer A",
                email="a@a.com",
                roles=[f"editor::{org_a_id}"],
            ),
        )

        upsert_by(
            User.find_one(User.email == "ab@a-and-b.com"),
            User(
                name="Reader ab",
                email="ab@a-and-b.com",
                roles=[
                    f"viewer::{org_a_id}",
                    f"viewer::{org_b_id}",
                ],
            ),
        )

        folder_query = And(
            NoteFolder.name == "root 1 a",  # ty: ignore[invalid-argument-type]
            NoteFolder.parent_id == None,  # noqa: E711 # ty: ignore[invalid-argument-type]
            NoteFolder.organization_id == org_a_id,  # ty: ignore[invalid-argument-type]
        )
        upsert_by(
            NoteFolder.find_one(folder_query),
            NoteFolder(
                name="root 1 a",
                parent_id=None,
                organization_id=org_a_id,
            ),
        )


if __name__ == "__main__":
    main()
