"""add notifications table and is_read to assistant_messages

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notifications table using raw SQL to avoid enum type conflicts
    op.execute("""
        CREATE TABLE notifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            is_one_shot BOOLEAN NOT NULL DEFAULT TRUE,
            related_entity_type VARCHAR(50),
            related_entity_id UUID,
            extra_data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'])

    # Add is_read to assistant_messages (existing messages treated as read)
    op.add_column('assistant_messages',
        sa.Column('is_read', sa.Boolean, nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('assistant_messages', 'is_read')
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
