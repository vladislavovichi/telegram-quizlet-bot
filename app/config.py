from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = Field("123:abc-def", description="Telegram bot token")
    DB_DSN: str = Field(
        "postgresql+asyncpg://postgres:postgres@db:5432/bot_db",
        description="SQLAlchemy DSN",
    )
    REDIS_DSN: str = "redis://localhost:6379/0"
    REDIS_PREFIX: str = "tgbot"
    REDIS_TTL_SEC: int = 900
    NEURALNET_URL: str = "http://neuralnet:8000"
    HINT_ENDPOINT: str = f"{NEURALNET_URL}/neuralnet/model"

    model_config = {
        "env_file": "config/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
