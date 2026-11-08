from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash-lite"
    ai_external_enabled: bool = False
    ai_daily_investigation_limit: int = Field(10, ge=0, le=1000)
    ai_global_daily_request_limit: int = Field(50, ge=0, le=10000)
    ai_request_cooldown_seconds: int = Field(5, ge=1, le=3600)
    ai_timeout_seconds: int = Field(12, ge=1, le=15)
    workspace_token: SecretStr | None = None
    database_url: SecretStr | None = None
    database_url_unpooled: SecretStr | None = None
    frontend_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator('frontend_origins')
    @classmethod
    def exact_origins(cls, origins):
        for origin in origins:
            url = urlsplit(origin)
            local = url.hostname in {'localhost', '127.0.0.1', '::1'}
            if (not url.hostname or '*' in origin or url.username or url.password
                    or url.path or url.query or url.fragment
                    or (url.scheme != 'https' and not (local and url.scheme == 'http'))):
                raise ValueError('Use exact HTTPS frontend origins without paths or trailing slash; HTTP is local-only')
        return origins

    model_config = SettingsConfigDict(
        # Neon writes at the repo root; explicit backend overrides remain supported.
        # Process environment variables take precedence over every dotenv file.
        env_file=(
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / ".env.local",
            PROJECT_ROOT / "backend" / ".env",
        ),
        extra="ignore",
    )


settings = Settings()
