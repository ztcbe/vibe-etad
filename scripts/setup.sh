#!/usr/bin/env bash
set -euo pipefail

echo "=== zvibe backend setup ==="

# Create .env if not exists
if [ ! -f backend/.env ]; then
    echo "Creating .env from .env.example..."
    cp backend/.env.example backend/.env
    echo "  -> Edit backend/.env with your settings"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
cd backend
pip install --break-system-packages -r requirements.txt 2>/dev/null || pip install -r requirements.txt
cd ..

# Start database
echo "Starting PostgreSQL..."
docker compose up -d db
sleep 3

# Run migrations
echo "Running migrations..."
cd backend
python -m alembic upgrade head
cd ..

echo ""
echo "=== Setup complete ==="
echo "Run 'make dev' to start the server"
echo "Run 'make test' to run all tests"
