"""agent run state machine and legacy compatibility

Revision ID: 0002_agent_run_state
Revises: cde15cf6bb6e
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_agent_run_state"
down_revision: str | Sequence[str] | None = "cde15cf6bb6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_legacy_compatibility_columns() -> None:
    conversation_columns = _column_names("conversations")
    if conversation_columns and "user_id" not in conversation_columns:
        with op.batch_alter_table("conversations") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
            batch_op.create_index("ix_conversations_user_id", ["user_id"], unique=False)

    message_columns = _column_names("messages")
    if message_columns:
        with op.batch_alter_table("messages") as batch_op:
            if "sdk_item_json" not in message_columns:
                batch_op.add_column(sa.Column("sdk_item_json", sa.Text(), nullable=True))
            if "is_visible" not in message_columns:
                batch_op.add_column(
                    sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("1"))
                )

    user_columns = _column_names("users")
    if user_columns:
        with op.batch_alter_table("users") as batch_op:
            if "is_admin" not in user_columns:
                batch_op.add_column(
                    sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0"))
                )
            if "is_active" not in user_columns:
                batch_op.add_column(
                    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
                )
            if "last_login_at" not in user_columns:
                batch_op.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))


def upgrade() -> None:
    _add_legacy_compatibility_columns()
    columns = _column_names("agent_runs")
    if not columns:
        return

    with op.batch_alter_table("agent_runs") as batch_op:
        if "execution_id" not in columns:
            batch_op.add_column(sa.Column("execution_id", sa.String(36), nullable=True))
        if "claimed_at" not in columns:
            batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        if "cancel_requested_at" not in columns:
            batch_op.add_column(sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
        if "cancelled_at" not in columns:
            batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        if "partial_output" not in columns:
            batch_op.add_column(sa.Column("partial_output", sa.Text(), nullable=True))
        if "version" not in columns:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")))
        if "event_seq" not in columns:
            batch_op.add_column(sa.Column("event_seq", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.alter_column(
            "status", existing_type=sa.String(30), nullable=False, server_default="pending"
        )
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )

    unique_items = sa.inspect(op.get_bind()).get_unique_constraints("agent_runs")
    has_execution_unique = any(
        item.get("column_names") == ["execution_id"] for item in unique_items
    )
    if not has_execution_unique:
        with op.batch_alter_table("agent_runs") as batch_op:
            batch_op.create_unique_constraint("uq_agent_runs_execution_id", ["execution_id"])

    op.execute(
        sa.text(
            """
            UPDATE agent_runs
            SET status = 'interrupted',
                finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                error_message = COALESCE(
                    error_message,
                    '应用升级时检测到未完成运行，已标记为 interrupted'
                ),
                version = version + 1
            WHERE status = 'running'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE agent_runs
            SET finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP)
            WHERE status IN ('completed', 'failed', 'cancelled', 'timeout', 'interrupted')
            """
        )
    )


def downgrade() -> None:
    columns = _column_names("agent_runs")
    if not columns:
        return

    op.execute(
        sa.text(
            """
            UPDATE agent_runs
            SET status = CASE
                    WHEN status = 'pending' THEN 'running'
                    WHEN status IN ('cancelled', 'timeout', 'interrupted') THEN 'failed'
                    ELSE status
                END,
                started_at = COALESCE(started_at, created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    unique_constraints = {
        item.get("name") for item in sa.inspect(op.get_bind()).get_unique_constraints("agent_runs")
    }
    with op.batch_alter_table("agent_runs") as batch_op:
        if "uq_agent_runs_execution_id" in unique_constraints:
            batch_op.drop_constraint("uq_agent_runs_execution_id", type_="unique")
        for name in (
            "event_seq",
            "version",
            "partial_output",
            "cancelled_at",
            "cancel_requested_at",
            "claimed_at",
            "execution_id",
        ):
            if name in columns:
                batch_op.drop_column(name)
        batch_op.alter_column(
            "status", existing_type=sa.String(30), nullable=False, server_default="running"
        )
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
