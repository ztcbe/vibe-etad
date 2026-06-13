#!/usr/bin/env bash
set -euo pipefail

PG_BIN=/usr/lib/postgresql/16/bin

echo "=========================================="
echo "  zvibe - Docker Startup"
echo "=========================================="

# 1. Init PostgreSQL
echo "[1/5] Initializing PostgreSQL..."
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    su postgres -c "$PG_BIN/initdb -D $PGDATA"
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
    echo "host all all ::1/128 trust" >> "$PGDATA/pg_hba.conf"
fi

# 2. Start PostgreSQL
echo "[2/5] Starting PostgreSQL..."
su postgres -c "$PG_BIN/pg_ctl -D $PGDATA -l /tmp/pg.log start"
for i in $(seq 1 20); do
    su postgres -c "$PG_BIN/pg_isready -q" && break
    sleep 0.5
done
echo "     PostgreSQL ready"

# 3. Setup database
echo "[3/5] Setting up database..."
su postgres -c "$PG_BIN/psql -U postgres -d postgres -c \"CREATE ROLE zvibe WITH LOGIN PASSWORD 'zvibe' CREATEDB;\""
su postgres -c "$PG_BIN/psql -U postgres -d postgres -c \"CREATE DATABASE zvibe OWNER zvibe;\""
su postgres -c "$PG_BIN/psql -U postgres -d zvibe -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
echo "     Database ready"

# 4. Run migrations
echo "[4/5] Running migrations..."
cd /app/backend
python -m alembic upgrade head
echo "     Migrations complete"

# 5. Seed demo data
echo "[5/5] Seeding demo data..."
python ../scripts/seed_demo.py 2>/dev/null || echo "     (seed skipped)"

echo ""
echo "=========================================="
echo "  zvibe ready at http://localhost:8080"
echo "  Demo: linh / demo123456"
echo "=========================================="
echo ""

cd /app/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
