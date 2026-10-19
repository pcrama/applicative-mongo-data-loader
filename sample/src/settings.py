from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Notes As A Service App"
    admin_email: str = "admin@test.local"
    mongo_initdb_root_username: str = "root"
    mongo_initdb_root_password: str = "Test1234"

settings = Settings()
