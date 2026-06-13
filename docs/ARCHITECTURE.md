# zvibe — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vanilla JS)                 │
│  index.html  ←→  api.js  ←→  REST /api/*                │
│  chat.js     ←→  WebSocket /ws/chats/{id}               │
│  Hash router: #/auth, #/home, #/matches, #/chat/{id}    │
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
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLAlchemy 2.0 (async)              │   │
│  └──────────────────────┬───────────────────────────┘   │
└─────────────────────────┼───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│           PostgreSQL + pgvector                          │
│  14 tables: users, profiles, matches, chat, etc.        │
└─────────────────────────────────────────────────────────┘
```

## Data Model (14 tables)

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Auth + account | email, password_hash, role, status, date_of_birth |
| `user_profiles` | Dating profile | display_name, gender, dating_goal, hobbies (JSONB), preferences (JSONB), completeness_score, visibility_status |
| `profile_embeddings` | Vector search | embedding (pgvector 1536d), embedding_model |
| `likes` | One-way like | from_user_id, to_user_id, status (active/cancelled) |
| `matches` | Mutual match | user_a_id, user_b_id, status, last_message_at |
| `recommendations` | AI suggestions | user_id, candidate_user_id, score, reason_codes, status |
| `chat_messages` | 1-1 chat | match_id, sender_user_id, content, message_type, status |
| `assistant_sessions` | AI chat session | user_id, state (JSONB: onboarding_step, pending_confirmation), summary |
| `assistant_messages` | AI chat history | session_id, role (user/assistant/tool), content, metadata |
| `ai_memories` | Long-term AI memory | user_id, memory_type (profile_fact/preference/etc), key, value |
| `media_assets` | Uploaded files | user_id, url, purpose (avatar/chat_attachment), mime_type |
| `reports` | User reports | reporter_user_id, reported_user_id, category, status |
| `blocks` | User blocks | blocker_user_id, blocked_user_id, reason |
| `ai_tool_logs` | Audit trail | user_id, session_id, agent_name, tool_name, input/output, latency_ms |

## Agent Architecture (Google ADK)

```
CoordinatorAgent (root)
  Tools: get_my_profile, calculate_profile_completeness, update_my_profile
  Instruction: Vietnamese — general chat, profile onboarding, routing to subs

  ├── MatchmakerAgent (sub)
  │     Tools: calculate_profile_completeness, search_candidates, like_candidate, pass_candidate, list_my_matches
  │     Instruction: Vietnamese — matching workflow, always check completeness first
  │
  └── ConversationCoachAgent (sub)
        Tools: get_match_context, generate_suggested_replies
        Instruction: Vietnamese — conversation advice, reply suggestions
        Also callable directly from suggest-reply API (bypasses coordinator)
```

**LLM adapter**: `LiteLlm` from ADK (backed by litellm) configured for VNGCloud MaaS via `openai/` provider prefix with custom `api_base`. Replaces the previous custom `VngCloudLlm(BaseLlm)` adapter.

**Session storage**: `DatabaseSessionService` (ADK) using the main PostgreSQL database. Persists agent conversation state across server restarts. Initialized at app startup via `lifespan`, shared across all requests. See `modules/assistant/session.py`.

**Tool context injection**: Python `contextvars` pass DB session + user_id to ADK tools without modifying ADK internals.

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

## WebSocket Protocol

Endpoint: `/ws/chats/{match_id}?token=<jwt>`

### Client → Server
| Action | Payload |
|---|---|
| `send_message` | `{content, message_type}` |
| `typing_started` | `{}` |
| `typing_stopped` | `{}` |
| `mark_read` | `{message_ids: [uuid]}` |

### Server → Client
| Event | Payload |
|---|---|
| `message_created` | `{id, match_id, sender_user_id, content, status, created_at}` |
| `typing_started` | `{match_id, user_id}` |
| `typing_stopped` | `{match_id, user_id}` |
| `message_read` | `{match_id, message_ids, reader_user_id}` |
| `mutual_match_created` | `{match_id, user}` |
| `match_unavailable` | `{match_id, reason}` |
| `error` | `{code, message}` |

## Frontend Architecture

- **SPA with hash router**: `#/auth`, `#/home`, `#/matches`, `#/chat/{id}`, `#/profile`, `#/admin`
- **State**: Global `State` object with token, user, profile, completeness, active chat
- **API client**: Auto-attach JWT, auto-refresh on 401
- **WebSocket**: Auto-reconnect with 3s backoff, REST fallback on failure
- **Design**: From `ui_design/`, paper texture background, sketch borders, watercolor aesthetic, Caveat + DM Sans fonts
