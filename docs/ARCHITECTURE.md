# zvibe — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vanilla JS)                 │
│  index.html  ←→  api.js  ←→  REST /api/*                │
│  chat.js     ←→  WebSocket /ws/chats/{id}               │
│  notifications.js ←→ WebSocket /ws/notifications         │
│  Hash router: #/auth, #/home, #/matches, #/chat/{id},   │
│               #/notifications, #/profile, #/admin        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend                         │
│                                                         │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────────────┐ │
│  │  Auth   │ │ Profiles │ │ Media  │ │   Assistant   │ │
│  │  JWT    │ │ CRUD     │ │ Upload │ │   ADK Agents  │ │
│  └─────────┘ └──────────┘ └────────┘ └──────┬────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌────────┐        │          │
│  │ Matching│ │   Chat   │ │ Admin  │   ┌────▼────────┐ │
│  │ Scoring │ │ REST+WS  │ │ Stats  │   │ VNGCloud    │ │
│  └─────────┘ └──────────┘ └────────┘   │ MaaS LLM    │ │
│                                         └─────────────┘ │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────────┐ │
│  │   Bot    │ │Notifications │ │    EventBus          │ │
│  │Auto-reply│ │ REST + WS    │ │ (in-process async)   │ │
│  └──────────┘ └──────────────┘ └─────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLAlchemy 2.0 (async)              │   │
│  └──────────────────────┬───────────────────────────┘   │
└─────────────────────────┼───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│           PostgreSQL + pgvector                          │
│  15 tables: users, profiles, matches, chat, notifs, etc.│
└─────────────────────────────────────────────────────────┘
```

## Data Model (15 tables)

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Auth + account | username, password_hash, role, status, date_of_birth, is_bot, account_source, last_active_at |
| `user_profiles` | Dating profile | display_name, gender, interested_in, dating_goal, hobbies (JSONB), preferences (JSONB), completeness_score, visibility_status |
| `profile_embeddings` | Vector search | embedding (pgvector 1536d), embedding_model |
| `likes` | One-way like | from_user_id, to_user_id, status (active/cancelled) |
| `matches` | Mutual match | user_a_id, user_b_id, status, last_message_at, last_message_preview |
| `recommendations` | AI suggestions | user_id, candidate_user_id, score, reason_codes, explanation, status |
| `chat_messages` | 1-1 chat | match_id, sender_user_id, content, message_type, status |
| `assistant_sessions` | AI chat session | user_id, state (JSONB), summary |
| `assistant_messages` | AI chat history | session_id, user_id, role (user/assistant/tool/system), content, metadata, is_read |
| `ai_memories` | Long-term AI memory | user_id, memory_type (profile_fact/preference/etc), key, value, confidence_score |
| `media_assets` | Uploaded files | user_id, url, purpose (avatar/chat_attachment), mime_type, size_bytes |
| `notifications` | In-app notifications | user_id, type, title, body, is_read, is_one_shot, related_entity_type/id, extra_data (JSONB) |
| `reports` | User reports | reporter_user_id, reported_user_id, category, status |
| `blocks` | User blocks | blocker_user_id, blocked_user_id, reason |
| `ai_tool_logs` | Audit trail | user_id, session_id, agent_name, tool_name, input/output, latency_ms |

## Event Bus

In-process async `EventBus` (`common/events.py`) for cross-module communication. Events are fired as background tasks.

| Event | Emitted by | Consumed by |
|---|---|---|
| `like_received` | matching service | notifications service (push to user), bot handlers (auto-like back) |
| `match_created` | matching service | notifications service (push to both users), bot handlers (send icebreaker) |
| `message_received` | chat service | notifications service (push unread badge), bot handlers (auto-reply) |
| `match_unavailable` | matching service | notifications service (notify both users) |

Handlers are registered during app startup via `register_event_handlers()` and `register_bot_handlers()`.

## Agent Architecture (Google ADK)

```
CoordinatorAgent (root)
  Tools: get_my_profile, calculate_profile_completeness, update_my_profile,
         update_my_avatar, find_user_by_name, check_relationship_status,
         list_matched_profiles, list_my_matches, get_matched_user_profile,
         get_candidate_profile, get_recent_suggestions, get_notifications
  Instruction: Vietnamese — general chat, profile onboarding, routing to subs

  ├── MatchmakerAgent (sub)
  │     Tools: calculate_profile_completeness, search_candidates,
  │            like_candidate, pass_candidate, list_my_matches,
  │            list_matched_profiles, find_user_by_name,
  │            check_relationship_status, get_matched_user_profile,
  │            get_candidate_profile, get_recent_suggestions
  │     Instruction: Vietnamese — matching workflow, always check completeness first
  │
  └── ConversationCoachAgent (sub)
        Tools: get_match_context, generate_suggested_replies,
               find_user_by_name, check_relationship_status, list_my_matches
        Instruction: Vietnamese — conversation advice, reply suggestions
        Also callable directly from suggest-reply API (bypasses coordinator)
```

**BotAgent** (separate, not part of coordinator tree):
- Tools: `get_my_bot_profile`, `get_bot_match_context`
- Used for demo bot auto-replies. Primary path is direct litellm call (single-turn), ADK agent kept for future multi-turn extension.
- Triggered by event handlers: auto-reply on `message_received`, auto-like on `like_received`, icebreaker on `match_created`.

**LLM adapter**: `LiteLlm` from ADK (backed by litellm) configured for VNGCloud MaaS via `openai/` provider prefix with custom `api_base`. Each agent can use different model/API key via per-agent env vars (fallback to global `LLM_*`).

**Per-agent LLM config** (in `config.py`):
| Agent | Env prefix | Default model | Temperature | Max output |
|---|---|---|---|---|
| Coordinator | `COORDINATOR_*` | `LLM_MODEL` | 0.8 | 1500 |
| Matchmaker | `MATCHMAKER_*` | `LLM_MODEL` | 0.7 | 1500 |
| ConversationCoach | `COACH_*` | `LLM_MODEL` | 0.9 | 1000 |
| Bot | `BOT_*` | `LLM_MODEL` | 0.9 | 250 |

**Session storage**: `DatabaseSessionService` (ADK) using the main PostgreSQL database. Persists agent conversation state across server restarts. Initialized at app startup via `lifespan`, shared across all requests. See `modules/assistant/session.py`.

**Tool context injection**: Python `contextvars` (`current_db`, `current_user_id`, `current_session_id`) pass DB session + user info to ADK tools without modifying ADK internals.

**Routing**: CoordinatorAgent uses ADK's auto-delegation (LLM-driven based on sub-agent `description` fields). The ConversationCoachAgent can also be invoked directly from `POST /api/chats/{id}/suggest-reply` without going through the coordinator.

## Scoring Algorithm

```
final_score = hard_filter_pass * (
  location_score       * 0.15 +
  dating_goal_score    * 0.20 +
  age_score            * 0.10 +
  interest_similarity  * 0.20 +
  personality_similarity * 0.20 +
  dealbreaker_score    * 0.15
)

score_tier: ≥80 → high (sage), 60-79 → medium (gold), <60 → low (ink-faint)
```

**Hard filters** (fail → score 0, excluded): gender/interested_in mismatch, age out of 2-way range, blocked.

**Interest similarity**: Jaccard coefficient of hobbies sets.

**Personality similarity**: 60% embedding cosine similarity + 40% communication_style match (when embeddings available), else communication_style only.

## WebSocket Protocol

### Chat WebSocket: `/ws/chats/{match_id}?token=<jwt>`

#### Client → Server
| Action | Payload |
|---|---|
| `send_message` | `{content, message_type}` |
| `typing_started` | `{}` |
| `typing_stopped` | `{}` |
| `mark_read` | `{message_ids: [uuid]}` |

#### Server → Client
| Event | Payload |
|---|---|
| `message_created` | `{id, match_id, sender_user_id, content, status, created_at}` |
| `typing_started` | `{match_id, user_id}` |
| `typing_stopped` | `{match_id, user_id}` |
| `message_read` | `{match_id, message_ids, reader_user_id}` |
| `mutual_match_created` | `{match_id, user}` |
| `match_unavailable` | `{match_id, reason}` |
| `error` | `{code, message}` |

### Notification WebSocket: `/ws/notifications?token=<jwt>`

Global per-user WebSocket for real-time push notifications.

#### Client → Server
| Action | Payload |
|---|---|
| `ping` | `{action: "ping"}` |

#### Server → Client
| Event | Payload |
|---|---|
| `pong` | `{event: "pong"}` |
| `notification` | `{id, type, title, body, related_entity_type, related_entity_id, extra_data, created_at}` |
| `assistant_message` | `{role, content, metadata}` |
| `unread_message` | `{match_id, sender_name, preview}` |

## Bot System

Demo bot users (`is_bot=True`, `account_source="seed"`) simulate real user behavior:

1. **Auto-like**: When a human likes a bot, bot instantly likes back → creates mutual match
2. **Auto-reply**: When bot receives a message, waits 2-8s (random), then generates contextual reply using LLM with bot's profile persona
3. **Icebreaker**: When a new match is created with a bot, sends first message after 3-10s delay
4. **Anti-loop**: Bot-bot interactions are skipped to prevent infinite loops
5. **Typing indicator**: Bot broadcasts `typing_started`/`typing_stopped` before/after reply generation

Bot reply uses direct litellm call (simpler/more reliable than ADK for single-turn). Bot's system prompt is built from its profile data + match context.

## Frontend Architecture

- **SPA with hash router**: `#/auth`, `#/home`, `#/matches`, `#/chat/{id}`, `#/notifications`, `#/profile`, `#/admin`
- **State**: Global `State` object with token, user, profile, completeness, active chat
- **API client**: Auto-attach JWT, auto-refresh on 401
- **WebSocket**: Auto-reconnect with 3s backoff, REST fallback on failure
- **Notification WS**: Separate global connection for real-time push
- **Design**: From `ui_design/`, paper texture background, sketch borders, watercolor aesthetic, Caveat + DM Sans fonts
