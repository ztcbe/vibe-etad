"""email → username

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", new_column_name="username")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=False)


def downgrade() -> None:
    op.alter_column("users", "username", new_column_name="email")
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
