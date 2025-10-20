from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    BOT_TOKEN: str = Field("", description="Telegram bot token")
    DB_DSN: str = Field("sqlite+aiosqlite:///./bot.db", description="SQLAlchemy DSN")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
