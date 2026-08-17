from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "Qualive Audience Intelligence"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="APP_DEBUG")
    host: str = Field(default="0.0.0.0", alias="APP_HOST")
    port: int = Field(default=8000, alias="APP_PORT")
    secret: str = Field(default="change-me", alias="APP_SECRET")
    timezone: str = "UTC"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    api_v1_prefix: str = "/api/v1"
    allow_registration: bool = Field(default=True, alias="APP_ALLOW_REGISTRATION")
    docs_enabled: bool = Field(default=True, alias="APP_DOCS_ENABLED")
    allowed_hosts_raw: str = Field(default="*", alias="APP_ALLOWED_HOSTS")
    sessions_dir: str = Field(default="sessions", alias="SESSIONS_DIR")
    dev_admin_email: str = Field(default="admin@example.com", alias="DEV_ADMIN_EMAIL")
    dev_admin_password: str = Field(default="admin", alias="DEV_ADMIN_PASSWORD")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="inviter", alias="POSTGRES_DB")
    postgres_user: str = Field(default="inviter", alias="POSTGRES_USER")
    postgres_password: str = Field(default="inviter", alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str | None = Field(default=None, alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    celery_broker_db: int = Field(default=0, alias="CELERY_BROKER_DB")
    celery_result_db: int = Field(default=1, alias="CELERY_RESULT_DB")

    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="APP_CORS_ORIGINS",
    )

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @computed_field
    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [host.strip() for host in self.allowed_hosts_raw.split(",") if host.strip()]
        return hosts or ["*"]

    @computed_field
    @property
    def database_url(self) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        database = quote(self.postgres_db, safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{database}"

    @computed_field
    @property
    def sync_database_url(self) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        database = quote(self.postgres_db, safe="")
        return f"postgresql+psycopg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{database}"

    def _redis_url(self, database: int) -> str:
        auth = f":{quote(self.redis_password, safe='')}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{database}"

    @computed_field
    @property
    def redis_url(self) -> str:
        return self._redis_url(self.redis_db)

    @computed_field
    @property
    def celery_broker_url(self) -> str:
        return self._redis_url(self.celery_broker_db)

    @computed_field
    @property
    def celery_result_backend(self) -> str:
        return self._redis_url(self.celery_result_db)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
