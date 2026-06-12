# zvibe — API Reference

Base URL: `http://localhost:8000/api`

All responses follow standard format:
```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

Error response:
```json
{
  "success": false,
  "data": null,
  "error": {"code": "ERROR_CODE", "message": "Human-readable message", "details": {}},
  "meta": {}
}
```

---

## Auth

### `POST /auth/register`
Register new account (age ≥18, username ≥3 chars).
```json
// Request
{"username": "linh", "password": "...", "confirm_password": "...", "date_of_birth": "2000-01-01"}
// Response
{"success": true, "data": {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}}
```

### `POST /auth/login`
Login with username + password.
```json
// Request
{"username": "linh", "password": "..."}
// Response — same as register
```

### `POST /auth/refresh`
Rotate tokens.
```json
// Request
{"refresh_token": "..."}
// Response — new token pair
```

### `POST /auth/logout`
Revoke refresh token.
```json
// Request
{"refresh_token": "..."}
```

### `GET /auth/me`
Get current user info + profile completeness.

---

## Profiles

### `GET /profile/me`
Full profile (all fields including private preferences).

### `PATCH /profile/me`
Partial update. Send only fields to change.
```json
{"display_name": "Linh", "city": "Đà Lạt", "hobbies": ["Cà phê", "Sách"]}
```

### `GET /profile/me/completeness`
Profile completeness with breakdown and missing fields (v0.2 §3.1).
```json
{
  "completeness_score": 80,
  "breakdown": {
    "basic_info": {"score": 30, "max": 30},
    "dating_goal": {"score": 15, "max": 15},
    "personality_hobbies": {"score": 10, "max": 20},
    "preferences": {"score": 10, "max": 20},
    "bio_summary": {"score": 15, "max": 15}
  },
  "missing_fields": ["hobbies_min_3", "preferred_distance_km"]
}
```

### `GET /profile/{user_id}`
Public profile only — display_name, age, city, avatar_url, public_summary, dating_goal, top_hobbies.
Returns 404 `PROFILE_NOT_AVAILABLE` if blocked or hidden.

---

## Media

### `POST /media/upload`
Upload avatar or chat attachment (multipart/form-data).
```
file: <binary>
purpose: avatar | chat_attachment
```
Response: `{"media_id": "uuid", "url": "/media/uploads/uuid.jpg", "purpose": "avatar"}`

---

## AI Assistant

### `POST /assistant/sessions`
Create new assistant conversation.
```json
// Request
{"title": "Trợ lý hẹn hò"}
```

### `GET /assistant/sessions`
List user's sessions (newest first).

### `GET /assistant/sessions/{session_id}/messages`
Get conversation history.

### `POST /assistant/chat`
Send message to AI. Core endpoint.
```json
// Request
{"session_id": "uuid", "message": "Tìm cho mình người hợp vibe đi", "context": {}}
// Response
{
  "message": "Mình tìm được 3 người khá hợp với bạn...",
  "actions": [{"type": "candidate_cards", "payload": {"cards": [...]}}],
  "requires_confirmation": false,
  "confirmation_action": null
}
```

Action types: `candidate_cards`, `profile_summary_card`, `confirmation_request`, `match_celebration`, `system_notice`, `quick_actions`.

---

## Matching

### `POST /matches/search`
Search candidates with scoring.
```json
// Request
{"limit": 5, "filters": {}}
// Response — array of candidate cards
[{
  "type": "candidate", "candidate_user_id": "uuid",
  "display_name": "Khang", "age": 29, "city": "Đà Lạt",
  "score": 87, "score_tier": "high",
  "reasons": ["Cả hai đều yêu thiên nhiên..."],
  "considerations": ["Khang làm việc theo ca..."],
  "reason_codes": ["shared_interests", "same_dating_goal"],
  "like_status": "none"
}]
```

### `GET /matches/recommendations?limit=5`
Get latest recommendations.

### `POST /matches/{candidate_user_id}/like`
Like a candidate. Returns `{"is_mutual": true, "match_id": "..."}` if they already liked you.

### `POST /matches/{candidate_user_id}/pass`
Pass on a candidate.

### `GET /matches`
List matches in 3 groups (v0.2 §3.3):
```json
{
  "matched": [{"match_id": "...", "user": {...}, "last_message": {...}, "unread_count": 1}],
  "pending_sent": [{"user": {...}, "liked_at": "..."}],
  "pending_received": []
}
```

### `GET /matches/{match_id}`
Match detail with public profile.

### `POST /matches/{match_id}/unmatch`
End a match.

---

## Chat

### `GET /chats/{match_id}/messages?limit=50&before_id=uuid`
Message history (cursor-based pagination).

### `POST /chats/{match_id}/messages`
Send message via REST (fallback for WebSocket).
```json
// Request
{"content": "Chào bạn! 👋", "message_type": "text"}
```

### `POST /chats/{match_id}/suggest-reply`
Get AI-suggested replies (2-3 items, ≤35 words each).
```json
// Request
{"tone": "natural"}  // natural, humorous, subtle, proactive, gentle, concise
// Response
{"suggestions": ["Chào bạn...", "Mình thấy..."]}
```

### WebSocket `ws://host:8000/ws/chats/{match_id}?token=<jwt>`
Real-time chat — see ARCHITECTURE.md for event protocol.

---

## Admin

All require admin role.

### `GET /admin/users?page=1&page_size=20`
Paginated user list with profile info.

### `GET /admin/reports?page=1&page_size=20`
Paginated report list.

### `GET /admin/stats`
Dashboard: `{"total_users": N, "active_users": N, "total_matches": N, "open_reports": N}`

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request |
| 401 | Unauthorized (invalid/missing token) |
| 403 | Forbidden (not participant, not admin) |
| 404 | Not found |
| 409 | Conflict (email exists, already liked) |
| 422 | Validation error |

## Error Codes

| Code | Description |
|---|---|
| `EMAIL_EXISTS` | Email already registered |
| `INVALID_CREDENTIALS` | Wrong email or password |
| `ACCOUNT_DISABLED` | Account suspended |
| `PROFILE_NOT_AVAILABLE` | Profile hidden/blocked |
| `CANDIDATE_NOT_FOUND` | User not found |
| `ALREADY_LIKED` | Duplicate like |
| `MATCH_NOT_PARTICIPANT` | Access denied to chat |
| `MATCH_INACTIVE` | Cannot message after unmatch |
| `MATCH_NOT_FOUND` | Match doesn't exist or not yours |
