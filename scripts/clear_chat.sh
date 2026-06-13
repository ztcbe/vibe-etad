#!/usr/bin/env bash
# Clear all chat data for user "linh" (or specified user) to reset testing state.
# Usage: ./scripts/clear_chat.sh [username]
set -euo pipefail
cd "$(dirname "$0")/.."

USERNAME="${1:-linh}"

python3 - "$USERNAME" << 'PYEOF'
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DB_URL = "postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe"
username = sys.argv[1]

async def main():
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        # Find user
        result = await conn.execute(
            text("SELECT u.id, u.username, p.display_name FROM users u LEFT JOIN user_profiles p ON p.user_id = u.id WHERE u.username = :un"),
            {"un": username},
        )
        user = result.fetchone()
        if not user:
            print(f"❌ User '{username}' not found")
            return

        uid = str(user[0])
        print(f"🧹 Clearing chat data for: {user[1]} (id={uid}, name={user[2]})")

        # Count before
        counts = {}
        for table in ("assistant_sessions", "assistant_messages", "ai_tool_logs",
                      "events", "sessions", "user_states"):
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :uid"), {"uid": uid}
            )
            counts[table] = result.scalar()

        # Delete: ADK tables first (FK dependencies)
        deleted = {}
        for table in ("events", "sessions", "user_states"):
            result = await conn.execute(
                text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": uid}
            )
            deleted[table] = result.rowcount

        # App tables
        for table in ("assistant_messages", "ai_tool_logs", "assistant_sessions"):
            result = await conn.execute(
                text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": uid}
            )
            deleted[table] = result.rowcount

        # Summary
        print(f"\n{'Table':<25} {'Before':>6} {'Deleted':>6}")
        print("-" * 40)
        total_before = 0
        total_deleted = 0
        for table in counts:
            d = deleted.get(table, 0)
            print(f"{table:<25} {counts[table]:>6} {d:>6}")
            total_before += counts[table]
            total_deleted += d
        print("-" * 40)
        print(f"{'TOTAL':<25} {total_before:>6} {total_deleted:>6}")

        print(f"\n✅ Done. {total_deleted} records deleted for {username}.")

    await engine.dispose()

asyncio.run(main())
PYEOF
