from bson import ObjectId
from bunnet.operators import Eq
from mongoloader import make_pipeline, FindOne
from sample.src.models import Organization, NoteFolder, User


def test_make_pipeline_two_elements() -> None:
    assert make_pipeline(
        {
            "org": FindOne(
                Organization,
                Eq(Organization.id, ObjectId("000011112222333344445555")).query,
            ),
            "parent": FindOne(
                NoteFolder,
                Eq(NoteFolder.id, ObjectId("aaaabbbbccccddddeeeeffff")).query,
            ),
        }
    ) == (
        Organization,
        [
            {
                "$match": {
                    "_id": ObjectId("000011112222333344445555"),
                },
            },
            {
                "$limit": 1,
            },
            {
                "$project": {
                    "kind": {
                        "$literal": "org",
                    },
                    "doc": "$$ROOT",
                },
            },
            {
                "$unionWith": {
                    "coll": "NoteFolder",
                    "pipeline": [
                        {
                            "$match": {
                                "_id": ObjectId("aaaabbbbccccddddeeeeffff"),
                            },
                        },
                        {
                            "$limit": 1,
                        },
                        {
                            "$project": {
                                "kind": {
                                    "$literal": "parent",
                                },
                                "doc": "$$ROOT",
                            },
                        },
                    ],
                },
            },
        ],
    )


def test_make_pipeline_three_elements() -> None:
    assert make_pipeline(
        {
            "org": FindOne(
                Organization,
                Eq(Organization.id, ObjectId("000011112222333344445555")).query,
            ),
            "user": FindOne(
                User,
                Eq(User.email, "me@example.com").query,
            ),
            "parent": FindOne(
                NoteFolder,
                Eq(NoteFolder.id, ObjectId("aaaabbbbccccddddeeeeffff")).query,
            ),
        }
    ) == (
        Organization,
        [
            {
                "$match": {
                    "_id": ObjectId("000011112222333344445555"),
                },
            },
            {
                "$limit": 1,
            },
            {
                "$project": {
                    "kind": {
                        "$literal": "org",
                    },
                    "doc": "$$ROOT",
                },
            },
            {
                "$unionWith": {
                    "coll": "User",
                    "pipeline": [
                        {
                            "$match": {
                                "email": "me@example.com",
                            },
                        },
                        {
                            "$limit": 1,
                        },
                        {
                            "$project": {
                                "kind": {
                                    "$literal": "user",
                                },
                                "doc": "$$ROOT",
                            },
                        },
                    ],
                },
            },
            {
                "$unionWith": {
                    "coll": "NoteFolder",
                    "pipeline": [
                        {
                            "$match": {
                                "_id": ObjectId("aaaabbbbccccddddeeeeffff"),
                            },
                        },
                        {
                            "$limit": 1,
                        },
                        {
                            "$project": {
                                "kind": {
                                    "$literal": "parent",
                                },
                                "doc": "$$ROOT",
                            },
                        },
                    ],
                },
            },
        ],
    )
