"""create meeting agent tables

Revision ID: 0001
Revises:
Create Date: 2026-07-26

Creates all tables needed by this service.

Upstream tables (meetings, audit_logs, notifications, meeting_updates) are
created with CREATE TABLE IF NOT EXISTS so that this migration is safe whether
the DB is brand-new (local Docker) or already has those tables (shared/Render).

The 5 agent-owned tables are always created fresh.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Upstream / dependency tables — safe to run on existing databases
    # because CREATE TABLE IF NOT EXISTS is a no-op when they exist.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title       VARCHAR(255),
            meeting_url TEXT,
            meeting_date DATE,
            start_time  TIME,
            end_time    TIME,
            platform    VARCHAR(50),
            meeting_id  VARCHAR(255),
            passcode    VARCHAR(255),
            status      VARCHAR(50),
            updated_at  TIMESTAMP,
            email_id    VARCHAR(255) UNIQUE,
            organizer   VARCHAR(255),
            description TEXT,
            time_zone   VARCHAR(50),
            created_at  TIMESTAMP DEFAULT now()
        )
    """)

    # Self-heal existing databases from the failed previous deploy
    op.execute("""
        ALTER TABLE meetings 
        ADD COLUMN IF NOT EXISTS email_id VARCHAR(255),
        ADD COLUMN IF NOT EXISTS organizer VARCHAR(255),
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS time_zone VARCHAR(50),
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now();
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            meeting_id  UUID,
            action      VARCHAR(255),
            details     TEXT,
            created_at  TIMESTAMP DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            meeting_id  UUID,
            message     TEXT,
            type        VARCHAR(50),
            created_at  TIMESTAMP DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS meeting_updates (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            meeting_id  UUID,
            old_status  VARCHAR(50),
            new_status  VARCHAR(50),
            created_at  TIMESTAMP DEFAULT now()
        )
    """)

    # ------------------------------------------------------------------
    # Tables owned by this Meeting Agent service
    # ------------------------------------------------------------------
    op.create_table(
        "meeting_transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "meeting_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_points", sa.Text(), nullable=True),
        sa.Column("follow_up", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "meeting_action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("deadline", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "meeting_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "meeting_attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("participant", sa.String(255), nullable=True),
        sa.Column("join_time", sa.DateTime(), nullable=True),
        sa.Column("leave_time", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("bot_joined", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("meeting_attendance")
    op.drop_table("meeting_decisions")
    op.drop_table("meeting_action_items")
    op.drop_table("meeting_reports")
    op.drop_table("meeting_transcripts")
    # Only drop upstream tables if this service created them
    op.execute("DROP TABLE IF EXISTS meeting_updates")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS meetings")
