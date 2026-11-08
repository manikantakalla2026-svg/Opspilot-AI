from pydantic import SecretStr

from app.core.config import Settings
from app.main import database_engine, settings


def test_dotenv_precedence_and_secret_redaction(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    root = tmp_path / ".env.local"
    override = tmp_path / "backend.env"
    root.write_text("DATABASE_URL=postgresql://user:root-secret@localhost/db\n")
    override.write_text("DATABASE_URL=postgresql://user:override-secret@localhost/db\n")
    config = Settings(_env_file=(root, override))
    assert "override-secret" in config.database_url.get_secret_value()
    assert "override-secret" not in repr(config)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:process-secret@localhost/db")
    assert "process-secret" in Settings(_env_file=root).database_url.get_secret_value()


def test_engine_preserves_pooler_and_ssl(monkeypatch):
    monkeypatch.setattr(settings, "database_url", SecretStr(
        "postgresql://user:secret@ep-example-pooler.neon.tech/db?sslmode=require"
    ))
    engine = database_engine()
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.host == "ep-example-pooler.neon.tech"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()


def test_production_origins_are_explicit_and_https(monkeypatch):
    from pydantic import ValidationError
    import pytest
    monkeypatch.setenv('FRONTEND_ORIGINS', '["https://opspilot-demo.pages.dev"]')
    assert Settings(_env_file=None).frontend_origins == ['https://opspilot-demo.pages.dev']
    for origin in ['*', 'https://*.pages.dev', 'http://public.example', 'https://example.com/', 'https://user:secret@example.com']:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, frontend_origins=[origin])
