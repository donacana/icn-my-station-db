from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    ws_push_interval_seconds: float = 5.0


settings = Settings()
