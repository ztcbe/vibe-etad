# ZVIBE — Backend Implementation Requirements v0.2

**Phiên bản:** v0.2 (bổ sung sau khi UI/UX hoàn thành)
**Dựa trên:** `project_requirements.md` (PRD v0.1, BA), `ui_extend_requirements.md`, và 6 deliverable UI/UX trong `ui_design/`
**Đối tượng đọc:** Backend Developer, AI/Agent Developer, DevOps, QA
**Mục đích:** Cụ thể hoá các API contract, WebSocket event, AI tool output, data model bổ sung **để khớp 1:1 với UI đã thiết kế**, và đề xuất kế hoạch triển khai theo sprint.

> Tài liệu này **không thay thế** PRD v0.1 (mục 6–23) — nó bổ sung phần "khớp nối với UI" và làm rõ những điểm UI cần mà PRD còn mô tả chung. Khi có mâu thuẫn, FR codes trong PRD v0.1 vẫn là nguồn chính, tài liệu này là phần chi tiết hoá/clarify.

---

## 1. Tổng hợp ánh xạ UI Screen ↔ Backend

| UI Screen (file trong `ui_design/`) | Backend module | API / WS chính | FR refs |
|---|---|---|---|
| Auth (`2_wireframe.html` tab Auth) | `auth` | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me` | FR-AUTH-001..004 |
| AI Assistant / Home (`3_high_fidelity_design.html`) | `assistant`, `profiles`, `matching` | `POST /assistant/chat`, `GET /profile/me/completeness` | FR-AI-001..006, FR-ONB-*, FR-PROFILE-004 |
| Candidate Card inline (component lib) | `assistant` (AI output) + `matching` | tool `search_candidates` → AI output `cards[]` | FR-MATCH-001..003, FR-AI-003 |
| Matches list (2 groups: matched/pending) | `matching` | `GET /matches`, `GET /matches/recommendations` | FR-MATCH-004/005, FR-CAND-001 |
| Chat 1-1 + AI Suggest tray | `chat`, `assistant` | `WS /ws/chats/{match_id}`, `GET/POST /chats/{match_id}/messages`, `POST /chats/{match_id}/suggest-reply` | FR-CHAT-*, FR-REPLY-* |
| Match celebration overlay | `matching` (event) | WS event `mutual_match_created` (mới — xem mục 4.4) | FR-MATCH-005 |
| Profile (mine / public) | `profiles` | `GET/PATCH /profile/me`, `GET /profile/{user_id}` (public — mới, xem mục 3.2) | FR-PROFILE-001..003, FR-CAND-001 |
| Unmatch/Report/Block modal | `matching`, `moderation` | `POST /matches/{id}/unmatch`, `POST /users/{id}/report`, `POST /users/{id}/block` | FR-MATCH-006, FR-SAFE-001/002 |
| Avatar upload (attach trong chat) | `media`/`profiles` (mới — xem mục 3.5) | `POST /media/upload` | ui_extend #4 |
| Admin (users/reports/logs) | `admin` | `GET /admin/users`, `GET /admin/reports`, `PATCH /admin/users/{id}/status`, `GET /admin/ai-logs` | FR-SAFE-005, mục 7.8 PRD |

---

## 2. Nguyên tắc bám sát UI (đọc trước khi code)

1. **Candidate card cần đủ field để render trực tiếp** — không để FE phải gọi thêm API để lấy `score`, `reasons`, `consider`, `avatar`. AI output `cards[]` (mục 11.4 PRD) phải bao gồm tất cả field trong bảng 4.2 bên dưới.
2. **Matches list phải trả về 2 nhóm rõ ràng** (`matched` vs `pending_sent`/`pending_received`) — không để FE tự suy luận từ raw `likes` + `matches`. Xem mục 3.3.
3. **Profile completeness** phải trả về cả số % và **danh sách field còn thiếu** (để AI biết hỏi tiếp gì, và UI có thể hiển thị gợi ý) — xem mục 3.1.
4. **Avatar/ảnh đại diện optional nhưng cần placeholder nhất quán** — backend trả `avatar_url: null` khi chưa có ảnh, FE tự render placeholder; **không** trả URL ảnh mặc định cứng từ BE.
5. **Status pill (Active/Paused/Hidden, Matched/Pending)** — mọi response liên quan profile/match phải trả enum string khớp đúng với giá trị đã định nghĩa trong PRD (`visibility_status`, `match.status`, `likes.status`) để FE map sang pill màu không cần transform.
6. **Suggestion tray luôn 2–3 item, không tự gửi** — `POST /chats/{match_id}/suggest-reply` trả mảng string thuần (đã đúng theo PRD mục 9.5); KHÔNG bọc thêm logic gửi.
7. **Mọi hành động nhạy cảm cần endpoint riêng + audit**, không gộp chung vào 1 endpoint generic — giữ đúng cấu trúc REST đã định nghĩa ở PRD mục 9.

---

## 3. API Contracts bổ sung/cụ thể hoá

### 3.1. `GET /profile/me/completeness`

UI cần: thanh tiến trình % (topbar) + AI cần biết hỏi tiếp gì (onboarding).

**Response:**
```json
{
  "success": true,
  "data": {
    "completeness_score": 80,
    "breakdown": {
      "basic_info": { "score": 30, "max": 30 },
      "dating_goal": { "score": 15, "max": 15 },
      "personality_hobbies": { "score": 10, "max": 20 },
      "preferences": { "score": 10, "max": 20 },
      "bio_summary": { "score": 15, "max": 15 }
    },
    "missing_fields": ["hobbies_min_3", "preferred_distance_km"]
  }
}
```
- `breakdown` dùng trọng số theo FR-PROFILE-004.
- `missing_fields` là enum cố định (xem Phụ lục A) — `ProfileBuilderAgent` dùng để quyết định câu hỏi tiếp theo (FR-ONB-002).

### 3.2. `GET /profile/{user_id}` — Public profile (mới)

UI `3_high_fidelity_design.html` tab Profile (public view) và candidate card chỉ hiển thị: avatar, tên+tuổi, dòng description ngắn, (nếu có context match) score + reasons.

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "display_name": "Khang",
    "age": 29,
    "city": "Đà Lạt",
    "avatar_url": null,
    "public_summary": "Yêu thiên nhiên, thích trekking và cà phê sáng sớm. Đang tìm một mối quan hệ nghiêm túc.",
    "dating_goal": "serious",
    "top_hobbies": ["Trekking", "Cà phê", "Đọc sách"]
  }
}
```
- **KHÔNG** trả: `email`, `lat/lng` chính xác, `deal_breakers`, `red_flags_to_avoid`, `preferences`, `private_summary`, `embedding_vector`. (FR-CAND-001, FR-SAFE-004)
- Nếu `user_id` đã bị `blocked` hai chiều hoặc `visibility_status != active` → trả `404` với error code `PROFILE_NOT_AVAILABLE` (map sang banner "không còn khả dụng" trong UI).

### 3.3. `GET /matches` — chia 2 nhóm theo wireframe

UI `2_wireframe.html`/`3_high_fidelity_design.html` tab Matches yêu cầu 2 group: "Đã match" và "Đã thích, đang chờ".

**Response:**
```json
{
  "success": true,
  "data": {
    "matched": [
      {
        "match_id": "uuid",
        "user": { "user_id": "uuid", "display_name": "Khang", "age": 29, "avatar_url": null },
        "last_message": { "content": "Hẹn gặp cuối tuần nha! ☕️", "created_at": "2026-06-10T08:00:00Z", "sender_user_id": "uuid" },
        "unread_count": 1,
        "matched_at": "2026-06-08T10:00:00Z"
      }
    ],
    "pending_sent": [
      { "user": { "user_id": "uuid", "display_name": "Huy", "age": 28, "avatar_url": null }, "liked_at": "2026-06-11T09:00:00Z" }
    ],
    "pending_received": []
  }
}
```
- `pending_sent`: user đã like, chưa có phản hồi → click mở `/profile/{user_id}` (read-only), **không** mở chat (đúng nguyên tắc mutual-like mới chat).
- `pending_received`: candidate đã like user nhưng user chưa phản hồi — **MVP có cần hiển thị không?** → đưa vào mục 7 (Open Questions), vì PRD không nói rõ UI có hiển thị mục này; wireframe hiện chỉ có 2 group. Đề xuất: backend vẫn trả field này (empty array nếu không dùng) để không breaking change khi PO chốt.
- `last_message: null` nếu chưa có tin nhắn → FE hiển thị "Chưa có tin nhắn — bắt đầu chat?" (đúng theo wireframe).

### 3.4. `POST /assistant/chat` — bổ sung action types cho UI

PRD mục 9.3 đã định nghĩa response cơ bản. Bổ sung **enum đầy đủ cho `actions[].type`** để FE render đúng component theo `4_component_library.html`:

| `type` | UI component tương ứng | payload |
|---|---|---|
| `candidate_cards` | Candidate Card (mục 4.2) | `{ "cards": [...] }` |
| `profile_summary_card` | Card tóm tắt profile khi onboarding xong (Journey A bước 6) | `{ "profile": {...}, "completeness": 80 }` |
| `confirmation_request` | Modal/inline xác nhận trước hành động nhạy cảm | `{ "action": "like_candidate", "target": {...}, "confirm_text": "Bạn muốn thích Khang chứ?" }` |
| `match_celebration` | Overlay 💞 trong prototype | `{ "match_id": "uuid", "user": {...} }` |
| `system_notice` | bubble cảnh báo (danger-soft) — vd "không thể chia sẻ thông tin riêng tư" | `{ "level": "info\|warning", "text": "..." }` |
| `quick_actions` | Quick action buttons trong context panel | `{ "actions": ["search_candidates","view_profile","list_matches"] }` |

**`requires_confirmation: true`** → FE render `confirmation_request` card với 2 nút (Đồng ý/Hủy). Khi user bấm "Đồng ý", FE gửi lại `POST /assistant/chat` với `message` = nội dung xác nhận (vd "Đúng vậy, thích luôn đi") — **không có endpoint "confirm" riêng**, giữ luồng hội thoại tự nhiên (đúng prototype).

### 3.5. `POST /media/upload` (mới)

UI yêu cầu nút 📎 trong chat input để đính kèm ảnh (avatar hoặc ảnh gửi AI) — ui_extend_requirements #4.

**Request:** `multipart/form-data`, field `file` (image/jpeg, image/png, ≤5MB), `purpose`: `avatar` | `chat_attachment`.

**Response:**
```json
{
  "success": true,
  "data": { "media_id": "uuid", "url": "/media/uuid.jpg", "purpose": "avatar" }
}
```
- Nếu `purpose=avatar` → set `user_profiles.avatar_url` luôn (1 avatar chính tại 1 thời điểm, MVP không cần album).
- Storage: local/private object storage theo PRD 1.4. Validate MIME + size + (basic) kích thước tối thiểu để tránh ảnh quá nhỏ/placeholder giả.
- **Không** chạy moderation ảnh nâng cao ở MVP (ngoài phạm vi PRD 2.2), nhưng cần check MIME type hợp lệ để tránh upload file thực thi.

---

## 4. WebSocket Contract chi tiết (`/ws/chats/{match_id}`)

PRD 14.4 đã liệt kê event names. Bổ sung **payload schema** + mapping UI behavior:

### 4.1. `message_created`
```json
{ "event": "message_created", "data": { "id": "uuid", "match_id": "uuid", "sender_user_id": "uuid", "content": "...", "status": "sent", "created_at": "..." } }
```
→ Append vào `chat-scroll`, auto-scroll xuống.

### 4.2. `typing_started` / `typing_stopped`
```json
{ "event": "typing_started", "data": { "match_id": "uuid", "user_id": "uuid" } }
```
→ Hiện/ẩn `typing-indicator` (3-dot bounce) trong UI Chat 1-1. FE debounce: gửi `typing_started` khi user nhập, `typing_stopped` sau 3s không gõ hoặc khi gửi message.

### 4.3. `message_delivered` / `message_read`
```json
{ "event": "message_read", "data": { "match_id": "uuid", "message_ids": ["uuid1","uuid2"], "reader_user_id": "uuid" } }
```
→ FE update message status icon (✓✓). **Could-have** theo PRD (FR-CHAT-003) — không block các milestone khác nếu chưa kịp.

### 4.4. `mutual_match_created` (mới — cần bổ sung vào PRD 14.4)
Khi user A like B và B đã like A trước đó (xảy ra ngoài WS chat hiện tại, thường qua `/assistant/chat` hoặc `/matches/{id}/like`), backend cần **push real-time** tới cả 2 user nếu họ đang online (qua một WS connection chung cho notification, hoặc broadcast tới `/ws/chats/{match_id}` mới tạo):
```json
{ "event": "mutual_match_created", "data": { "match_id": "uuid", "user": { "user_id":"uuid", "display_name":"Khang", "avatar_url": null } } }
```
→ Trigger `match_celebration` overlay (mục 3.4) trên FE đang mở app.
- **Quyết định kỹ thuật cần chốt**: MVP có 1 WS kênh "notification" riêng (per-user) ngoài kênh chat per-match không? Đề xuất: có — `/ws/notifications` (per-user) để nhận `mutual_match_created`, `match_unavailable` (khi không ở trong màn chat đó), `report_status_update` (cho admin). Việc này KHÔNG có trong PRD gốc → đưa vào Open Questions (mục 7) để PO/Tech Lead chốt trước khi code WS layer.

### 4.5. `match_unavailable`
```json
{ "event": "match_unavailable", "data": { "match_id": "uuid", "reason": "unmatched|blocked|user_disabled" } }
```
→ FE hiện banner đỏ trong chat-scroll + disable input (đúng `2_wireframe.html` ghi chú Edge case #4 PRD mục 17).

### 4.6. `error`
```json
{ "event": "error", "data": { "code": "RATE_LIMITED", "message": "Bạn gửi tin nhắn quá nhanh, vui lòng thử lại." } }
```

---

## 5. AI Tool Output Contract — khớp UI Component Library

### 5.1. Candidate card object (trong `cards[]` của `/assistant/chat` và tool `search_candidates`)

```json
{
  "type": "candidate",
  "candidate_user_id": "uuid",
  "display_name": "Khang",
  "age": 29,
  "city": "Đà Lạt",
  "avatar_url": null,
  "dating_goal": "serious",
  "score": 87,
  "score_tier": "high",
  "reasons": ["Cả hai đều yêu thiên nhiên, thích trekking và cà phê sáng sớm."],
  "considerations": ["Khang làm việc theo ca, có thể lệch giờ sinh hoạt."],
  "reason_codes": ["shared_interests", "same_dating_goal"],
  "like_status": "none"
}
```
- `score_tier`: enum `high` (≥80, → màu `sage`), `medium` (60-79, → `coral`), `low` (<60, → `gold`) — **tính sẵn ở backend** theo bảng threshold trong `6_design_handoff_spec.md` mục 4.3, để FE không cần hardcode logic màu.
- `reasons` / `considerations`: **array of string**, ngắn (1 câu), do AI sinh dựa trên `reason_codes` + public summaries — KHÔNG chứa raw private data (FR-MATCH-003).
- `like_status`: `none | liked | passed` — để FE disable nút tương ứng nếu user đã hành động trước đó (vd reload lại candidate card cũ).

### 5.2. `suggest-reply` response — khớp Suggestion Tray

PRD 9.5 đã đúng format (`{"suggestions": ["...", "..."]}`). Bổ sung:
- Luôn trả **đúng 2 hoặc 3** item (không 1, không >3) — UI tray hard-code layout cho 2-3 item.
- Mỗi suggestion ≤ ~35 từ tiếng Việt (tránh tràn UI bubble suggestion, theo FR-REPLY prompt "không quá dài").
- Nếu `tone` không được truyền → default `"natural"`.

### 5.3. Confirmation flow output (mục 3.4 `confirmation_request`)

Khi AI cần xác nhận trước `like_candidate`, `unmatch_user`, `report_user`, `block_user`, hoặc update field nhạy cảm:
```json
{
  "text": "Bạn muốn thích Khang chứ? Mình sẽ gửi lời thích cho bạn ấy nha 💌",
  "intent": "like_candidate",
  "cards": [],
  "requires_confirmation": true,
  "confirmation_action": {
    "tool_name": "like_candidate",
    "tool_args": { "candidate_user_id": "uuid" }
  }
}
```
- Backend **lưu `confirmation_action` vào session state** (assistant_sessions.state JSONB) với TTL ngắn (vd 5 phút). Khi user gửi message tiếp theo có ý xác nhận (AI tự nhận diện qua intent `general_chat` + context xác nhận, hoặc FE gửi kèm `context.confirm_pending: true`), agent thực thi `tool_name`/`tool_args` đã lưu.
- Nếu user đổi ý/không xác nhận trong TTL → session state tự xoá `confirmation_action`, không thực thi.

---

## 6. Data Model — bổ sung/điều chỉnh so với PRD mục 10

| Bảng | Thay đổi | Lý do (từ UI) |
|---|---|---|
| `user_profiles` | thêm `avatar_url` (nullable string) | Avatar placeholder + upload theo ui_extend #4 |
| `likes` | đảm bảo có index `(to_user_id, status)` và `(from_user_id, status)` | Truy vấn nhanh cho `pending_sent`/`pending_received` (mục 3.3) |
| `matches` | thêm computed/denormalized `last_message_at`, `last_message_preview` (hoặc query join) | Hiển thị preview trong Matches list mà không join nặng mỗi lần |
| `chat_messages` | đảm bảo `status` enum đúng `sent|delivered|read` để FE render đúng icon | FR-CHAT-003 |
| *(mới)* `media_assets` | `id, user_id, url, purpose(avatar|chat_attachment), mime_type, size_bytes, created_at` | API `/media/upload` (mục 3.5) |
| `assistant_sessions.state` | định nghĩa rõ schema con: `{ "pending_confirmation": {...}, "onboarding_step": "...", "active_match_id": "..." }` | Confirmation flow (mục 5.3) + onboarding state machine |

---

## 7. Open Questions cần chốt trước khi code (ưu tiên cho backend/AI)

Đây là tập con các câu hỏi từ PRD mục 21, **ưu tiên hoá lại** dựa trên việc UI đã hoàn thành và đang block backend:

1. **`pending_received` có hiển thị trong UI Matches không?** (PRD §21.1 Q2 đã trả lời "mutual-like mới chat" nhưng chưa rõ user có thấy ai đang like mình chưa match). Wireframe hiện tại chỉ có 2 group. → Cần PO chốt để quyết định API có trả `pending_received` đầy đủ object hay chỉ `count`.
2. **Kênh WS riêng cho notification** (`/ws/notifications`) cho `mutual_match_created` khi user không ở trong chat — có cần ở MVP hay match celebration chỉ hiện khi user **đang** trong luồng chat với AI (trường hợp trong prototype)? Ảnh hưởng kiến trúc WS (mục 4.4).
3. **Giới hạn upload ảnh đại diện**: 1 ảnh hay nhiều? Có cần crop/resize server-side không, hay FE crop trước khi upload? (ảnh hưởng `media_assets` schema và xử lý storage).
4. **Confirmation TTL & cách FE báo "user xác nhận"**: dùng tự nhiên ngôn ngữ (AI tự nhận biết "đúng vậy") hay FE gửi flag `confirm_pending: true` kèm message? Đề xuất ở mục 5.3 cần PO/Tech Lead duyệt vì ảnh hưởng prompt design của `ZvibeAssistantAgent`.
5. **`score_tier` thresholds** (80/60) — đã đề xuất khớp UI, cần confirm với PO/BA vì ảnh hưởng cảm nhận "độ hợp" hiển thị cho user.
6. Các câu hỏi kỹ thuật khác ở PRD §21.5 (vector DB, LLM provider, deploy, Docker, CI/CD) **vẫn còn mở** — cần chốt trước Milestone 1.

---

## 8. Đề xuất kế hoạch Sprint (bám Milestone PRD §20 + UI đã có)

| Sprint | Nội dung | UI tham chiếu để test |
|---|---|---|
| **S1 — Foundation** | Auth (FR-AUTH-001..004), `user_profiles` schema, `GET/PATCH /profile/me`, completeness API (3.1), `/media/upload` (3.5) | `2_wireframe.html` Auth + Profile |
| **S2 — AI Onboarding** | ADK setup, `ZvibeAssistantAgent` + `ProfileBuilderAgent`, tools `get_my_profile`/`update_my_profile`/`calculate_profile_completeness`, `POST /assistant/chat` với `profile_summary_card` | `5_clickable_prototype.html` luồng onboarding |
| **S3 — Matching** | `search_candidates`, scoring (PRD §12), `candidate_cards` output (5.1), like/pass, mutual match logic, `GET /matches` 2-group (3.3), confirmation flow (5.3) | candidate card trong `3_high_fidelity_design.html` + `4_component_library.html` |
| **S4 — Chat 1-1** | `matches` thread tạo khi mutual, `chat_messages`, WS `/ws/chats/{match_id}` (4.1–4.3, 4.5), `mutual_match_created` (4.4 — pending Q2) | Chat 1-1 + match celebration trong prototype |
| **S5 — AI Reply & Advice** | `suggest-reply` (5.2), `ConversationCoachAgent`, `get_match_context`, `ADV` constraints | Suggestion tray trong prototype |
| **S6 — Safety & Admin** | report/block (FR-SAFE-001/002), `SafetyAgent` guardrails, AI audit log, Admin APIs (users/reports/ai-logs), public profile endpoint (3.2) | Modal Unmatch/Report/Block + Admin wireframe |

---

## 9. Definition of Done bổ sung (theo UI)

Mỗi API/feature trong tài liệu này chỉ **Done** khi, ngoài DoD chung ở PRD §23:

- Response field names **khớp chính xác** với bảng contract ở mục 3/5 (để FE không cần transform thêm).
- Đã test với prototype `5_clickable_prototype.html` (thay mock data bằng API thật) cho ít nhất 1 happy path/screen.
- `score_tier`, `like_status`, `match.status`, `visibility_status` trả đúng enum để FE map trực tiếp sang `status-pill`/`score-badge` trong `4_component_library.html` không cần if/else phức tạp.
- Private fields (mục 3.2 danh sách "KHÔNG trả") được unit-test để đảm bảo không leak qua bất kỳ endpoint nào trả candidate/public profile.
