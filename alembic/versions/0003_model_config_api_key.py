from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_model_config_api_key"
down_revision: str | Sequence[str] | None = "0002_agent_run_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("model_configs")
    if not columns:
        return

    with op.batch_alter_table("model_configs") as batch_op:
        if "api_key" not in columns:
            batch_op.add_column(
                sa.Column("api_key", sa.Text(), nullable=True, comment="模型 API Key，由管理员后台配置")
            )
        if "api_key_env" in columns:
            batch_op.alter_column(
                "api_key_env",
                existing_type=sa.String(length=100),
                nullable=True,
                existing_comment="API Key 对应的环境变量名",
            )


def downgrade() -> None:
    columns = _column_names("model_configs")
    if not columns:
        return

    if "api_key_env" in columns:
        op.execute(
            sa.text(
                """
                UPDATE model_configs
                SET api_key_env = COALESCE(NULLIF(api_key_env, ''), 'MODEL_API_KEY')
                WHERE api_key_env IS NULL OR api_key_env = ''
                """
            )
        )
        with op.batch_alter_table("model_configs") as batch_op:
            batch_op.alter_column(
                "api_key_env",
                existing_type=sa.String(length=100),
                nullable=False,
                existing_comment="API Key 对应的环境变量名",
            )
            if "api_key" in columns:
                batch_op.drop_column("api_key")
