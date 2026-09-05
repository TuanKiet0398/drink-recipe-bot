from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    chroma_persist_dir: str = "./chroma_db"
    telegram_bot_token: str = ""
    database_url: str = "sqlite:///./local.db"
    admin_username: str = "admin"
    admin_password: str = "admin"
    telegram_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
