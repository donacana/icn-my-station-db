from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    ws_push_interval_seconds: float = 5.0

    # DB 접속 정보는 .env에서 읽는다 (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSLMODE)
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_sslmode: str = "require"

    def db_connect_kwargs(self) -> dict[str, str | int]:
        """psycopg.connect()에 넘길 인자. 필수 값이 없으면 값 없이 키 이름만 알려준다."""
        required = {
            "DB_HOST": self.db_host,
            "DB_NAME": self.db_name,
            "DB_USER": self.db_user,
            "DB_PASSWORD": self.db_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f".env에 값이 없습니다: {', '.join(missing)}")
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password.get_secret_value(),
            "sslmode": self.db_sslmode,
        }


settings = Settings()
