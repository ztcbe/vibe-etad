"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types
user_role = ENUM("user", "admin", name="userrole", create_type=True)
user_status = ENUM("active", "disabled", "deleted", name="userstatus", create_type=True)
dating_goal = ENUM("serious", "casual", "friends_first", "not_sure", name="datinggoal", create_type=True)
visibility_status = ENUM("active", "paused", "hidden", name="visibilitystatus", create_type=True)
like_status = ENUM("active", "cancelled", name="likestatus", create_type=True)
match_status = ENUM("active", "unmatched", "blocked", name="matchstatus", create_type=True)
rec_status = ENUM("suggested", "liked", "passed", "expired", name="recommendationstatus", create_type=True)
message_status = ENUM("sent", "delivered", "read", name="messagestatus", create_type=True)
message_type = ENUM("text", "image", name="messagetype", create_type=True)
assistant_role = ENUM("user", "assistant", "tool", "system", name="assistantrole", create_type=True)
memory_type = ENUM("profile_fact", "preference", "conversation_summary", "safety_note", name="memorytype", create_type=True)
media_purpose = ENUM("avatar", "chat_attachment", name="mediapurpose", create_type=True)
report_category = ENUM("harassment", "scam", "fake_profile", "sexual_misconduct", "hate_speech", "threats", "underage", "other", name="reportcategory", create_type=True)
report_status = ENUM("open", "reviewing", "resolved", "rejected", name="reportstatus", create_type=True)


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("status", user_status, nullable=False, server_default="active"),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("is_age_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # user_profiles
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("gender", sa.String(50)),
        sa.Column("interested_in", sa.String(50)),
        sa.Column("city", sa.String(100)),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("dating_goal", dating_goal),
        sa.Column("relationship_status", sa.String(50)),
        sa.Column("bio", sa.Text),
        sa.Column("personality_traits", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("hobbies", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("values", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("lifestyle", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("communication_style", sa.String(100)),
        sa.Column("deal_breakers", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("preferences", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("public_summary", sa.Text),
        sa.Column("private_summary", sa.Text),
        sa.Column("matching_summary", sa.Text),
        sa.Column("completeness_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("visibility_status", visibility_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # profile_embeddings
    op.create_table(
        "profile_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", sa.Text),  # pgvector — will alter below
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE profile_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.create_index("ix_profile_embeddings_user_id", "profile_embeddings", ["user_id"])

    # assistant_sessions
    op.create_table(
        "assistant_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("state", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assistant_sessions_user_id", "assistant_sessions", ["user_id"])

    # assistant_messages
    op.create_table(
        "assistant_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("assistant_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", assistant_role, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assistant_messages_session_id", "assistant_messages", ["session_id"])

    # ai_memories
    op.create_table(
        "ai_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", memory_type, nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", JSONB),
        sa.Column("confidence_score", sa.Float),
        sa.Column("source_message_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_memories_user_id", "ai_memories", ["user_id"])

    # likes
    op.create_table(
        "likes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("from_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", like_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_likes_from_status", "likes", ["from_user_id", "status"])
    op.create_index("ix_likes_to_status", "likes", ["to_user_id", "status"])
    op.create_index("ix_likes_from_to_unique", "likes", ["from_user_id", "to_user_id"], unique=True)

    # matches
    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_a_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_b_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", match_status, nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_preview", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_matches_user_a_id", "matches", ["user_a_id"])
    op.create_index("ix_matches_user_b_id", "matches", ["user_b_id"])

    # recommendations
    op.create_table(
        "recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("reason_codes", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("explanation", sa.Text),
        sa.Column("status", rec_status, nullable=False, server_default="suggested"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])

    # chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", UUID(as_uuid=True), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_type", message_type, nullable=False, server_default="text"),
        sa.Column("status", message_status, nullable=False, server_default="sent"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_match_id", "chat_messages", ["match_id"])

    # reports
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("reporter_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", UUID(as_uuid=True), sa.ForeignKey("matches.id", ondelete="SET NULL")),
        sa.Column("category", report_category, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", report_status, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reports_reporter_user_id", "reports", ["reporter_user_id"])
    op.create_index("ix_reports_reported_user_id", "reports", ["reported_user_id"])

    # blocks
    op.create_table(
        "blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("blocker_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocked_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_blocks_blocker_user_id", "blocks", ["blocker_user_id"])
    op.create_index("ix_blocks_blocked_user_id", "blocks", ["blocked_user_id"])

    # media_assets
    op.create_table(
        "media_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("purpose", media_purpose, nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_media_assets_user_id", "media_assets", ["user_id"])

    # ai_tool_logs
    op.create_table(
        "ai_tool_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("assistant_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input_sanitized", JSONB),
        sa.Column("output_summary", JSONB),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_tool_logs_user_id", "ai_tool_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("ai_tool_logs")
    op.drop_table("media_assets")
    op.drop_table("blocks")
    op.drop_table("reports")
    op.drop_table("chat_messages")
    op.drop_table("recommendations")
    op.drop_table("matches")
    op.drop_table("likes")
    op.drop_table("ai_memories")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_sessions")
    op.drop_table("profile_embeddings")
    op.drop_table("user_profiles")
    op.drop_table("users")

    op.execute("DROP EXTENSION IF EXISTS vector")

    report_status.drop(op.get_bind())
    report_category.drop(op.get_bind())
    media_purpose.drop(op.get_bind())
    memory_type.drop(op.get_bind())
    assistant_role.drop(op.get_bind())
    message_type.drop(op.get_bind())
    message_status.drop(op.get_bind())
    rec_status.drop(op.get_bind())
    match_status.drop(op.get_bind())
    like_status.drop(op.get_bind())
    visibility_status.drop(op.get_bind())
    dating_goal.drop(op.get_bind())
    user_status.drop(op.get_bind())
    user_role.drop(op.get_bind())
