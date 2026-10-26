from urllib.parse import quote_plus

import pytest
from bunnet import init_bunnet
from pymongo import MongoClient

from sample.src.models import NoteFolder, Organization, User, Note
from sample.src.settings import settings


@pytest.fixture(scope="session", autouse=True)
def initialize_bunnet():
    client = MongoClient(
        f"mongodb://{quote_plus(settings.mongo_initdb_root_username)}:{quote_plus(settings.mongo_initdb_root_password)}@localhost:27017"
    )
    database = client["app_test"]

    init_bunnet(
        database=database,
        document_models=[Note, NoteFolder, Organization, User],
    )

    yield

    client.drop_database("app_test")
    client.close()
