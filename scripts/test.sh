#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

# Ensure test DB exists
docker compose -f ../docker-compose.yml exec -T db psql -U zvibe -d postgres -c "CREATE DATABASE zvibe_test;" 2>/dev/null || true

SPRINT="${1:-all}"

case "$SPRINT" in
    s1)  TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_auth.py tests/test_profiles.py -v ;;
    s2)  TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_assistant.py -v ;;
    s3)  TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_matching.py -v ;;
    s4)  TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_chat.py -v ;;
    all) TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/ -v ;;
    *)   echo "Usage: $0 [s1|s2|s3|s4|all]"; exit 1 ;;
esac
