from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings


def build_engine(secret):
    if not secret:
        raise ValueError("Database is not configured")
    url = make_url(secret.get_secret_value())
    if url.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL is required")
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("An SSL connection is required")
    return create_engine(url.set(drivername="postgresql+psycopg"), pool_pre_ping=True,
                         pool_size=5, max_overflow=5,
                         connect_args={"connect_timeout": 8})


@lru_cache
def engine():
    return build_engine(settings.database_url)


def get_session():
    with Session(engine(), expire_on_commit=False) as session:
        yield session
