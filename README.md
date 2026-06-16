# zvibe — AI-first Dating App

> Hẹn hò có AI đồng hành — web-app ghép đôi lấy AI assistant làm trung tâm trải nghiệm.

## Tổng quan

zvibe thay thế form truyền thống và thao tác swipe bằng **hội thoại tự nhiên với AI**. Người dùng trò chuyện với AI assistant để:
- Tạo và cập nhật dating profile
- Tìm người phù hợp (AI đề xuất kèm giải thích)
- Nhận gợi ý trả lời tin nhắn trong chat 1-1
- Được tư vấn về các mối quan hệ
- Nhận thông báo real-time (like, match, tin nhắn mới)

**Tech stack:** FastAPI + PostgreSQL + pgvector + Google ADK + WebSocket (backend), Vanilla HTML/CSS/JS (frontend)

## Quick Start

```bash
# One command demo
./scripts/demo.sh

# Or step by step
make db-up          # Start PostgreSQL
make migrate        # Run DB migrations
make seed           # Seed 30 demo users
make dev            # Start dev server on :8000

# Open http://localhost:8000
# Login: linh / demo123456
```

## Project Structure

```
zvibe_be/
  backend/              # FastAPI backend
    app/
      main.py           # App entry, CORS, router wiring, lifespan, WS endpoints
      config.py         # Pydantic Settings (per-agent LLM config)
      dependencies.py   # Auth dependencies (JWT, admin, WS)
    db/
      models/           # SQLAlchemy 2.0 models (15 tables)
      session.py        # Async engine + session
      base.py           # Base model class
      enum_helper.py    # PostgreSQL enum helper
    modules/
      auth/             # Register, login, refresh, logout, me
      profiles/         # Profile CRUD, completeness, public profile
      media/            # Avatar/chat attachment upload
      assistant/        # AI chat with Google ADK agents
        agents/         # CoordinatorAgent → MatchmakerAgent, ConversationCoachAgent
        tools/          # profile_tools, matching_tools, chat_tools, notification_tools
        prompts/        # Vietnamese system prompts
        llm_adapter.py  # LiteLlm adapter for VNGCloud MaaS
        session.py      # ADK DatabaseSessionService
      matching/         # Search, like, pass, mutual match, unmatch
        scoring.py      # Hybrid scoring algorithm
      chat/             # REST + WebSocket 1-1 chat
        websocket.py    # WS handler with broadcast
      bot/              # Bot auto-reply + auto-match for demo users
        bot_agent.py    # BotAgent (ADK) + direct litellm reply generation
        context.py      # Bot match context builder
        handlers.py     # Event handlers: auto-reply, auto-like, icebreaker
        tools.py        # Bot-specific ADK tools
      notifications/    # In-app notifications + WebSocket push
        websocket.py    # Global per-user notification WS
        service.py      # Notification CRUD + event-driven handlers
      moderation/       # Report, block (models only)
      admin/            # User/report listing, stats
    common/             # Shared utilities
      errors.py         # AppError hierarchy + standard_response
      enums.py          # All enum types
      events.py         # In-process async EventBus
      pagination.py     # PaginatedResponse helper
      logging.py        # Logging setup
    migrations/         # Alembic (6 migrations)
    tests/              # ~6 test files (auth, profiles, assistant, matching, chat, bot)
  frontend/             # Vanilla JS SPA
    index.html          # Main shell (7 screens)
    css/main.css        # Design tokens + all styles
    assets/             # Static assets (favicon, mark, bg image)
    js/
      api.js            # HTTP client + auth
      app.js            # Router + global state
      auth.js           # Login/register
      assistant.js      # AI chat screen
      matches.js        # Matches list
      chat.js           # 1-1 chat + WebSocket
      notifications.js  # Notifications screen
      profile.js        # Profile + admin
      components/       # Toast, modal, celebration
  scripts/
    demo.sh             # One-command demo launcher
    setup.sh            # Full project setup
    seed_demo.py        # 30 demo users
    run_dev.sh          # Dev server
    deploy_agentbase.sh # AgentBase deployment
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
- **Real-time Notifications**: WebSocket push cho like, match, tin nhắn mới
- **Bot Demo Users**: Auto-reply, auto-like, icebreaker cho tài khoản demo
- **Safety**: Report, block, unmatch với confirmation modal
- **Admin Panel**: User/report listing, dashboard stats

## Running Tests

```bash
make test           # All tests
make test-s1        # Auth + Profiles
make test-s2        # AI Assistant
make test-s3        # Matching
make test-s4        # Chat
```

## API Docs

See [docs/API.md](docs/API.md) for full endpoint reference.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.
See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for dev guide.
