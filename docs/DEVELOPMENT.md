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

# Per-agent overrides (optional, fallback to LLM_* if not set)
COORDINATOR_LLM_MODEL=
MATCHMAKER_LLM_MODEL=
COACH_LLM_MODEL=
BOT_LLM_MODEL=

# Bot behavior
BOT_REPLY_DELAY_MIN=2.0
BOT_REPLY_DELAY_MAX=8.0
```

## Development

```bash
make dev           # Start server on :8000 (hot reload)
make test          # Run all tests
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
2. Tool uses `current_db`, `current_user_id`, `current_session_id` from `modules/assistant/tools/__init__.py`
3. Register tool in `modules/assistant/agents/__init__.py`
4. Tests: verify tool function signature (no required args — reads from contextvars)

### Event-driven features
- Use `common/events.py` EventBus for cross-module communication
- Register handlers in module's `register_*_handlers()` function
- Call registration during app `lifespan` startup
- Events: `like_received`, `match_created`, `message_received`, `match_unavailable`

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
make test-s1    # Auth + Profiles
make test-s2    # AI Assistant
make test-s3    # Matching
make test-s4    # Chat

# Bot tests
cd backend && TEST_DATABASE_URL="postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test" \
  pytest tests/test_bot.py -v

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
  index.html          # SPA shell (7 screens)
  css/main.css        # All styles
  assets/             # favicon, mark SVG, background image
  js/
    api.js            # HTTP client (auto JWT, auto refresh on 401)
    app.js            # Router + state
    auth.js           # Login/register
    assistant.js      # AI chat screen
    matches.js        # Matches list
    chat.js           # 1-1 chat + WS
    notifications.js  # Notifications screen
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

## Key Architecture Decisions

### Per-agent LLM config
Each agent (Coordinator, Matchmaker, Coach, Bot) can use a different model/API key via per-agent env vars. Fallback to global `LLM_*` if not set. See `config.py` for the resolver methods.

### Bot reply via direct litellm
Bot replies use direct `litellm.acompletion()` instead of ADK agent for simplicity and reliability. Single-turn text generation doesn't need ADK tool chaining. The ADK `BotAgent` builder is kept for potential future multi-turn bot behavior.

### In-process EventBus
Cross-module communication uses a simple in-process async EventBus rather than Redis/Celery. This keeps the architecture simple for a single-server deployment. If scaling to multiple processes, this would need replacement with a message broker.

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

### Bot not replying
- Check `LLM_API_KEY` is set
- Check user has `is_bot=True` in DB
- Check bot-bot prevention: both sender and recipient must not both be bots
- Check logs: `Bot {id} generating reply for match {id}`
