#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

# Ensure DB is up
docker compose -f ../docker-compose.yml ps db 2>/dev/null | grep -q "Up" || {
    echo "Starting database..."
    docker compose -f ../docker-compose.yml up -d db
    sleep 3
}

# Run migrations
python -m alembic upgrade head

echo "Starting zvibe API server on http://localhost:9000"
echo "API docs:   http://localhost:9000/docs"
echo "Frontend:   http://localhost:9000 (open ../frontend/index.html in browser)"
echo ""
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
