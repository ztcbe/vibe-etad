.PHONY: setup db-up db-down migrate seed demo test dev clean

# ── Setup ──────────────────────────────────────────────
setup:
	cd backend && pip install --break-system-packages -r requirements.txt

# ── Database ───────────────────────────────────────────
db-up:
	docker compose up -d db
	@echo "Waiting for PostgreSQL..."
	@sleep 3
	@docker compose exec db pg_isready -U zvibe || true

db-down:
	docker compose down

# ── Migrations ─────────────────────────────────────────
migrate:
	cd backend && python -m alembic upgrade head

migrate-test:
	cd backend && DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m alembic upgrade head

# ── Dev server ─────────────────────────────────────────
dev:
	cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Tests ──────────────────────────────────────────────
test:
	cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/ -v

test-s1:
	cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_auth.py tests/test_profiles.py -v

test-s2:
	cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_assistant.py -v

test-s3:
	cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_matching.py -v

test-s4:
	cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" python -m pytest tests/test_chat.py -v

# ── Docker all-in-one ──────────────────────────────────
docker-build:
	docker build -t zvibe:latest .

docker-run:
	docker run -d --name zvibe-app -p 8000:8000 zvibe:latest
	@echo "Waiting for startup..."
	@sleep 8
	@echo "zvibe ready at http://localhost:8000"

docker-stop:
	docker stop zvibe-app 2>/dev/null || true
	docker rm zvibe-app 2>/dev/null || true

docker-logs:
	docker logs -f zvibe-app

docker-rebuild: docker-stop docker-build docker-run

# ── Docker Compose (separate services) ──────────────────
docker-up:
	docker compose up -d

docker-build-compose:
	docker compose build

# ── Demo (one command) ─────────────────────────────────
demo:
	./scripts/demo.sh

# ── Seed demo data ─────────────────────────────────────
seed:
	cd backend && python ../scripts/seed_demo.py

# ── Clean ──────────────────────────────────────────────
clean:
	rm -rf backend/.pytest_cache backend/__pycache__ backend/**/__pycache__ backend/**/**/__pycache__ backend/uploads/*
