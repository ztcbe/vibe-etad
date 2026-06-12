# zvibe — AI-first Dating App

> Hẹn hò có AI đồng hành — web-app ghép đôi lấy AI assistant làm trung tâm trải nghiệm.

## Tổng quan

zvibe thay thế form truyền thống và thao tác swipe bằng **hội thoại tự nhiên với AI**. Người dùng trò chuyện với AI assistant để:
- Tạo và cập nhật dating profile
- Tìm người phù hợp (AI đề xuất kèm giải thích)
- Nhận gợi ý trả lời tin nhắn trong chat 1-1
- Được tư vấn về các mối quan hệ

**Tech stack:** FastAPI + PostgreSQL + pgvector + Google ADK (https://github.com/google/adk-python) + WebSocket (backend), Vanilla HTML/CSS/JS (frontend)

## Quick Start

```bash
# One command demo
./scripts/demo.sh

# Or step by step
make db-up          # Start PostgreSQL
make migrate        # Run DB migrations
make seed           # Seed 30 demo users
make dev            # Start dev server

# Open http://localhost:8000
# Login: linh / demo123456
```

## Project Structure

```
zvibe_be/
  backend/              # FastAPI backend
    app/
      main.py           # App entry, CORS, router wiring
      config.py         # Pydantic Settings
      dependencies.py   # Auth dependencies (JWT, admin)
    db/
      models/           # SQLAlchemy models (14 tables)
      session.py        # Async engine + session
    modules/
      auth/             # Register, login, refresh, logout, me
      profiles/         # Profile CRUD, completeness, public profile
      media/            # Avatar upload
      assistant/        # AI chat with Google ADK agents
        agents/         # ZvibeAssistant, ProfileBuilder, Matchmaker
        tools/          # Profile & matching tools for AI
        prompts/        # Vietnamese system prompts
        llm_adapter.py  # VNGCloud MaaS adapter
      matching/         # Search, like, pass, mutual match, unmatch
        scoring.py      # Hybrid scoring algorithm
      chat/             # REST + WebSocket 1-1 chat
        websocket.py    # WS handler with event system
      moderation/       # Report, block (models only)
      admin/            # User/report listing, stats
    common/             # Errors, enums, pagination, logging
    migrations/         # Alembic
    tests/              # 40 tests across S1-S4
  frontend/             # Vanilla JS SPA
    index.html          # Main shell (6 screens)
    css/main.css        # Design tokens + all styles
    js/
      api.js            # HTTP client + auth
      app.js            # Router + global state
      auth.js           # Login/register
      assistant.js      # AI chat screen
      matches.js        # Matches list
      chat.js           # 1-1 chat + WebSocket
      profile.js        # Profile + admin
      components/       # Toast, modal, celebration
  scripts/
    demo.sh             # One-command demo launcher
    setup.sh            # Full project setup
    seed_demo.py        # 30 demo users
    run_dev.sh          # Dev server
  docker-compose.yml    # PostgreSQL + pgvector
  Makefile              # make demo, make test, make seed
  docs/                 # This documentation
```

## Demo Accounts

| Username | Name | Password | Role |
|---|---|---|---|
| linh | Linh (27, Đà Lạt) | demo123456 | User |
| khang | Khang (29, Đà Lạt) | demo123456 | Match với Linh |
| thao | Thảo (26, HCM) | demo123456 | Match với Huy |
| admin | Admin | demo123456 | Admin |

## Key Features

- **AI Onboarding**: Chat với AI để tạo profile — không form dài
- **Smart Matching**: Hybrid scoring (location, goals, interests, personality, dealbreakers)
- **Candidate Cards**: AI đề xuất kèm % hợp, lý do, điểm cân nhắc
- **Mutual Match**: Thích 2 chiều → tự động tạo chat thread
- **Real-time Chat 1-1**: WebSocket với typing indicator, message status
- **AI Suggest Reply**: 2-3 gợi ý trả lời theo 6 tone
- **Safety**: Report, block, unmatch với confirmation modal
- **Admin Panel**: User/report list, dashboard stats

## Running Tests

```bash
make test           # All 40 tests
make test-s1        # Auth + Profiles
make test-s2        # AI Assistant
make test-s3        # Matching
make test-s4        # Chat
```

## API Docs

See [docs/API.md](docs/API.md) for full endpoint reference.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.
See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for dev guide.
