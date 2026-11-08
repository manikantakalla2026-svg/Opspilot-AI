"""Add isolated AI quota and cache tables; existing operational tables unchanged."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = 'b75_ai_analysis'
down_revision = 'a64bccfa6f4d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_usage',
        sa.Column('workspace', sa.String(30), primary_key=True),
        sa.Column('day', sa.String(10), nullable=False),
        sa.Column('requests', sa.Integer(), nullable=False),
        sa.Column('investigations', sa.Integer(), nullable=False),
        sa.Column('last_request', sa.DateTime(timezone=True)))
    op.create_table('ai_analyses',
        sa.Column('cache_key', sa.String(64), primary_key=True),
        sa.Column('incident_id', sa.Uuid(), sa.ForeignKey('incidents.id'), nullable=False),
        sa.Column('result', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('ai_analyses')
    op.drop_table('ai_usage')
