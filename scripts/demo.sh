#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════╗"
echo "║     🎯 zvibe — Demo Launcher            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Start PostgreSQL ──
echo "📦 Starting PostgreSQL..."
docker compose up -d db 2>&1 | grep -v "is up to date" || true
sleep 2

# Wait for healthy
for i in $(seq 1 15); do
  docker compose exec -T db pg_isready -U zvibe 2>/dev/null && break
  sleep 1
done
echo "   ✅ Database ready"

# ── 2. Run migrations ──
echo "📋 Running migrations..."
cd backend
python -m alembic upgrade head 2>&1 | tail -1
echo "   ✅ Migrations done"

# ── 3. Seed data (if not already) ──
echo "🌱 Checking demo data..."
USER_COUNT=$(docker compose exec -T db psql -U zvibe -d zvibe -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ' || echo "0")
if [ "$USER_COUNT" -lt 5 ] 2>/dev/null; then
  echo "🌱 Seeding 30 demo users..."
  python ../scripts/seed_demo.py 2>/dev/null
  echo "   ✅ Demo data seeded"
else
  echo "   ✅ Demo data already present ($USER_COUNT users)"
fi

# ── 4. Start server ──
echo ""
echo "══════════════════════════════════════════"
echo "  🚀 Starting zvibe on http://localhost:8000"
echo ""
echo "  👤 Demo login:"
echo "     Username: linh"
echo "     Password: demo123456"
echo ""
echo "  🤍 AI Assistant: http://localhost:8000"
echo "  📋 API Docs:     http://localhost:8000/docs"
echo "  💞 Matches:      http://localhost:8000/#/matches"
echo "══════════════════════════════════════════"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
