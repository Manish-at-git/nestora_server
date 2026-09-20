"""Typed application settings loaded from environment variables and a local .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Keep every environment setting in one validated, documented place."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str
    mysql_database: str = "nestora_auth"

    session_cookie_name: str = "nestora_session"
    csrf_cookie_name: str = "nestora_csrf"
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str | None = None
    session_ttl_hours: int = Field(default=168, ge=1, le=24 * 31)
    cors_origins: str = ""
    frontend_url: str = "http://localhost:5173"
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    encryption_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ENCRYPTION_KEY", "BANK_ENCRYPTION_KEY"),
    )

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_folder: str = "nestora"
    uploadthing_token: str | None = None
    uploadthing_node_binary: str = "node"

    @property
    def uploadthing_helper_path(self) -> Path:
        """Resolve the checked-in UploadThing bridge without cwd assumptions."""
        return Path(__file__).resolve().parent / "storage" / "providers" / "uploadthing_helper.mjs"

    # Brevo Transactional Email API Configuration
    brevo_api_key: str | None = None
    brevo_sender_email: str | None = None
    brevo_sender_name: str = "Nestora"

    # SMTP is optional in development, but production password reset delivery
    # requires all of these values to be configured.
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    initial_admin_email: str | None = None
    initial_admin_password: str | None = None

    @field_validator("session_cookie_domain", mode="before")
    @classmethod
    def blank_domain_is_none(cls, value: str | None) -> str | None:
        """Allow an empty .env value to mean a host-only cookie."""
        return value or None

    @property
    def async_database_url(self) -> str:
        """Build the SQLAlchemy async URL without hard-coding credentials in code."""
        return URL.create(
            "mysql+aiomysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    @property
    def sync_database_url(self) -> str:
        """Alembic uses PyMySQL synchronously while the API uses aiomysql asynchronously."""
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    @property
    def allowed_origins(self) -> list[str]:
        """Convert a readable comma-separated environment value into a CORS list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Create settings once so every module uses the same validated configuration."""
    return Settings()
