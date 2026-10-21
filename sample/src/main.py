from contextlib import asynccontextmanager
from urllib.parse import quote_plus

import sentry_sdk
from bunnet import init_bunnet
from fastapi import FastAPI
from pymongo import MongoClient

from .models import Note, NoteFolder, Organization, User
from .routes import router
from .settings import settings

sentry_sdk.init()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with MongoClient(
        f"mongodb://{quote_plus(settings.mongo_initdb_root_username)}:{quote_plus(settings.mongo_initdb_root_password)}@localhost:27017"
    ) as client:
        init_bunnet(
            database=client[settings.mongo_database],
            document_models=[Organization, User, NoteFolder, Note],
        )
        app.state.mongo_client = client
        yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)
