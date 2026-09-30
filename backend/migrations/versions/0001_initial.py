"""Initial monitoring schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_name", sa.String(80), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
    )
    op.create_index("ix_logs_timestamp", "logs", ["timestamp"])
    op.create_index("ix_logs_service_level_time", "logs", ["service_name", "level", "timestamp"])
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("incident_type", sa.String(40), nullable=False),
        sa.Column("service_name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("metric_name", sa.String(80), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("metric_evidence", sa.JSON(), nullable=False),
        sa.Column("log_excerpt", sa.JSON(), nullable=False),
        sa.Column("ai_explanation", sa.Text()),
        sa.Column("ai_recommendation", sa.JSON()),
        sa.Column("likely_cause", sa.Text()),
        sa.Column("uncertainty_note", sa.Text()),
        sa.Column("analysis_source", sa.String(20)),
        sa.Column("analysis_model", sa.String(80)),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])
    op.create_index(
        "uq_open_service_rule",
        "incidents",
        ["service_name", "incident_type"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "analysis_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_attempts_attempted_at", "analysis_attempts", ["attempted_at"])


def downgrade():
    op.drop_table("analysis_attempts")
    op.drop_table("incidents")
    op.drop_table("logs")
