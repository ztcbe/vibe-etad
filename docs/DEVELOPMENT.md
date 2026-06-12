# zvibe — Development Guide

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- VNGCloud MaaS API key (for AI features)

## Setup

```bash
# Clone + install
cd zvibe_be
./scripts/setup.sh

# Or manually
make db-up          # Start PostgreSQL + pgvector
make setup          # Install Python deps
make migrate        # Create tables
make seed           # 30 demo users
```

## Environment

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe
JWT_SECRET=<random-string>
LLM_API_KEY=<vngcloud-api-key>
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=google/gemma-4-31b-it
```

## Development

```bash
make dev           # Start server on :8000 (hot reload)
make test          # Run all tests
make test-s3       # Run specific sprint tests
```

## Project Conventions

### Backend layers
- **Router**: HTTP handling, dependency injection, response formatting
- **Service**: Business logic, DB queries, orchestration
- **Schemas**: Pydantic request/response models
- **Tools**: ADK-compatible callable functions for AI agent

### Code style
- Python: type hints on all function signatures
- SQLAlchemy 2.0 style: `Mapped[]` + `mapped_column()`
- Async everywhere: `async def` + `await` for DB and HTTP
- Vietnamese: system prompts and user-facing messages
- Response format: always use `standard_response(data=...)`

### Adding a new API endpoint
1. Add schemas in `modules/<name>/schemas.py`
2. Add business logic in `modules/<name>/service.py`
3. Add route in `modules/<name>/router.py`
4. Wire router in `app/main.py`
5. Add tests in `tests/test_<name>.py`

### Adding a new AI tool
1. Create tool function in `modules/assistant/tools/<name>_tools.py`
2. Tool uses `current_db` and `current_user_id` from `modules/assistant/tools/__init__.py`
3. Register tool in `modules/assistant/agents/__init__.py`
4. Tests: verify tool function signature (no required args — reads from contextvars)

## Database

### Create migration
```bash
cd backend && alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Reset demo data
```bash
docker compose down -v   # Wipes DB
docker compose up -d db
make migrate
make seed
```

## Testing

```bash
# All tests
make test

# By sprint
make test-s1    # Auth + Profiles (11)
make test-s2    # AI Assistant (8)
make test-s3    # Matching (15)
make test-s4    # Chat (6)

# Single test
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" \
  pytest tests/test_auth.py::test_register -v
```

Test database is `zvibe_test` — auto-created and truncated between tests.

## Frontend

Vanilla HTML/CSS/JS served from same port as backend.

```bash
# Frontend served automatically at http://localhost:8000
# Source files in frontend/
frontend/
  index.html          # SPA shell
  css/main.css        # All styles
  js/
    api.js            # HTTP client
    app.js            # Router + state
    auth.js           # Login/register
    assistant.js      # AI chat screen
    matches.js        # Matches list
    chat.js            # 1-1 chat + WS
    profile.js        # Profile + admin
    components/       # Toast, modal, celebration
```

### Design system
From `ui_design/4_component_library.html`:
- Colors: paper, ink, coral, teal, lavender, sage, gold, danger (with -soft variants)
- Fonts: Caveat (headings), DM Sans (body)
- Borders: 1.5px solid ink (components), 2px solid ink (cards/modals)
- Radius: 8px/12px/16px/100px (pill)
- Background: paper texture SVG noise filter

## Troubleshooting

### "Connect call failed" (port 5432)
```bash
docker compose up -d db
```

### "Missing credentials" (LLM)
Set valid `LLM_API_KEY` in `backend/.env`. AI features work but show fallback message without key.

### Frontend not loading
Check `frontend/` directory exists. Backend serves it automatically.

### Tests failing
```bash
# Recreate test DB
docker exec zvibe_be-db-1 psql -U zvibe -d postgres -c "DROP DATABASE IF EXISTS zvibe_test; CREATE DATABASE zvibe_test;"
```
