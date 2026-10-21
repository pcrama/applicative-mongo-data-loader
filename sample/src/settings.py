from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Notes As A Service App"
    mongo_initdb_root_username: str = "root"
    mongo_initdb_root_password: str = "Test1234"
    mongo_database: str = "notes_test"


settings = Settings()
