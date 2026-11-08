from alembic import context
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import build_engine
from app.models.entities import Base

secret = settings.database_url_unpooled
if not secret:
    raise ValueError('DATABASE_URL_UNPOOLED is required for migrations')
if '-pooler' in (make_url(secret.get_secret_value()).host or ''):
    raise ValueError('Migrations require a direct, unpooled connection')
engine = build_engine(secret)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
