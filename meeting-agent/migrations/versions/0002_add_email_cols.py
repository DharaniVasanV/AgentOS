"""add frontend columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Explicitly add the columns if they don't exist
    op.execute("""
        ALTER TABLE meetings 
        ADD COLUMN IF NOT EXISTS email_id VARCHAR(255),
        ADD COLUMN IF NOT EXISTS organizer VARCHAR(255),
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS time_zone VARCHAR(50),
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now();
    """)

def downgrade() -> None:
    pass
