from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    telegram_bot_token: str = ""
    database_url: str = "sqlite:///./local.db"
    admin_username: str = "admin"
    admin_password: str = "admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
