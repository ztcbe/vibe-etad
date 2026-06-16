"""Agent builder — creates ADK agent team with injected context and tools.

Agent Team Architecture:
  CoordinatorAgent (root)
  ├── MatchmakerAgent (sub) — profile analysis + candidate search + like/pass
  └── ConversationCoachAgent (sub) — match chat advice + reply suggestions

The coordinator receives all assistant chat and routes to specialists.
ConversationCoachAgent can also be invoked directly from suggest-reply API
(bypassing the coordinator).
"""
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai.types import GenerateContentConfig

from app.config import settings
from modules.assistant.llm_adapter import build_llm
from modules.assistant.tools import profile_tools, matching_tools, chat_tools, notification_tools


def build_coordinator_agent() -> LlmAgent:
    """Build the root CoordinatorAgent with its sub-agent team.

    Returns the root agent. Use this for assistant chat (/api/assistant/chat).
    """
    matchmaker = _build_matchmaker_agent()
    conversation_coach = _build_conversation_coach_agent()

    cfg = settings.coordinator_llm()
    coordinator = LlmAgent(
        name="CoordinatorAgent",
        description=(
            "Trợ lý hẹn hò zvibe — điều phối yêu cầu người dùng, "
            "xây dựng hồ sơ cá nhân, và chuyển đến chuyên gia phù hợp."
        ),
        model=build_llm(
            model=cfg["model"],
            api_key=cfg["api_key"],
            api_base=cfg["api_base"],
            max_tokens=cfg["max_tokens"],
        ),
        instruction=_COORDINATOR_INSTRUCTION,
        tools=[
            FunctionTool(profile_tools.get_my_profile),
            FunctionTool(profile_tools.calculate_profile_completeness),
            FunctionTool(profile_tools.update_my_profile),
            FunctionTool(profile_tools.update_my_avatar),
            FunctionTool(matching_tools.find_user_by_name),
            FunctionTool(matching_tools.check_relationship_status),
            FunctionTool(matching_tools.list_matched_profiles),
            FunctionTool(matching_tools.list_my_matches),
            FunctionTool(matching_tools.get_matched_user_profile),
            FunctionTool(matching_tools.get_candidate_profile),
            FunctionTool(matching_tools.get_recent_suggestions),
            FunctionTool(notification_tools.get_notifications),
        ],
        sub_agents=[matchmaker, conversation_coach],
        generate_content_config=GenerateContentConfig(
            temperature=settings.COORDINATOR_TEMPERATURE,
            max_output_tokens=settings.COORDINATOR_MAX_OUTPUT_TOKENS,
        ),
    )

    return coordinator


def build_conversation_coach_agent() -> LlmAgent:
    """Build the ConversationCoachAgent for direct invocation.

    Use this for suggest-reply API (/api/chats/{id}/suggest-reply)
    to bypass the coordinator.
    """
    return _build_conversation_coach_agent()


def _build_matchmaker_agent() -> LlmAgent:
    """Build MatchmakerAgent — handles matching and profile analysis."""
    cfg = settings.matchmaker_llm()
    return LlmAgent(
        name="MatchmakerAgent",
        description=(
            "Tìm kiếm người phù hợp, phân tích hồ sơ, và quản lý match "
            "(like/pass/xem danh sách match). Dùng khi user muốn tìm người "
            "hợp vibe, xem danh sách match, like, hoặc pass."
        ),
        model=build_llm(
            model=cfg["model"],
            api_key=cfg["api_key"],
            api_base=cfg["api_base"],
            max_tokens=cfg["max_tokens"],
        ),
        instruction=_MATCHMAKER_INSTRUCTION,
        tools=[
            FunctionTool(profile_tools.get_my_profile),
            FunctionTool(profile_tools.calculate_profile_completeness),
            FunctionTool(profile_tools.update_my_profile),
            FunctionTool(matching_tools.search_candidates),
            FunctionTool(matching_tools.like_candidate),
            FunctionTool(matching_tools.pass_candidate),
            FunctionTool(matching_tools.list_my_matches),
            FunctionTool(matching_tools.list_matched_profiles),
            FunctionTool(matching_tools.find_user_by_name),
            FunctionTool(matching_tools.check_relationship_status),
            FunctionTool(matching_tools.get_matched_user_profile),
            FunctionTool(matching_tools.get_candidate_profile),
            FunctionTool(matching_tools.get_recent_suggestions),
        ],
        generate_content_config=GenerateContentConfig(
            temperature=settings.MATCHMAKER_TEMPERATURE,
            max_output_tokens=settings.MATCHMAKER_MAX_OUTPUT_TOKENS,
        ),
    )


def _build_conversation_coach_agent() -> LlmAgent:
    """Build ConversationCoachAgent — helps user talk to matches."""
    cfg = settings.coach_llm()
    return LlmAgent(
        name="ConversationCoachAgent",
        description=(
            "Hỗ trợ người dùng trò chuyện với match — gợi ý tin nhắn trả lời, "
            "tư vấn cách nói chuyện, giúp phá băng. Dùng khi user cần lời "
            "khuyên về cách nhắn tin hoặc muốn gợi ý câu trả lời."
        ),
        model=build_llm(
            model=cfg["model"],
            api_key=cfg["api_key"],
            api_base=cfg["api_base"],
            max_tokens=cfg["max_tokens"],
        ),
        instruction=_CONVERSATION_COACH_INSTRUCTION,
        tools=[
            FunctionTool(chat_tools.get_match_context),
            FunctionTool(chat_tools.generate_suggested_replies),
            FunctionTool(matching_tools.find_user_by_name),
            FunctionTool(matching_tools.check_relationship_status),
            FunctionTool(matching_tools.list_my_matches),
        ],
        generate_content_config=GenerateContentConfig(
            temperature=settings.COACH_TEMPERATURE,
            max_output_tokens=settings.COACH_MAX_OUTPUT_TOKENS,
        ),
    )


# ── System Instructions ──────────────────────────────────────────────

_COORDINATOR_INSTRUCTION = """Bạn là "trợ lý zvibe" - dating copilot duy nhất của user.
[DANH TÍNH]
TUYỆT ĐỐI KHÔNG nhắc đến Coordinator, MatchmakerAgent hay ConversationCoachAgent. User không được biết về cơ chế nội bộ.
Danh xưng: theo cách user xưng hô, user gọi "mày" -> xưng "tao", user gọi "tôi" -> xưng "mình", etc.
[LUỒNG XỬ LÝ CHÍNH]
- Đầu phiên/Khi hỏi thông báo: Gọi `get_notifications()`. Báo tin tự nhiên nếu có.
- Khách mới: Chào -> `calculate_profile_completeness` -> Hướng dẫn tạo hồ sơ.
- Hỏi người cụ thể (theo tên):
  + Nếu người đó VỪA được đề xuất trong kết quả search_candidates gần nhất:
    -> Dùng thẳng candidate_user_id từ kết quả, KHÔNG gọi `find_user_by_name`.
  + Nếu không rõ: Gọi `get_recent_suggestions()` để kiểm tra danh sách đề xuất.
  + Nếu vẫn không có trong danh sách đề xuất: MẶC ĐỊNH gọi `check_relationship_status(name)`.
  + Nếu `not_found`: Gọi `list_matched_profiles()` -> So sánh tên gần đúng -> Hỏi xác nhận user.
- Hỏi tính cách người đã match: Gọi `get_matched_user_profile(name)`. (Nếu `ambiguous`/`no_fuzzy_match`, hiển thị list cho user chọn).
- Hỏi "ai đang chờ match/ai thích mình/ai đang chờ phản hồi": Gọi `list_my_matches()`. Báo pending_received (người thích bạn, bạn chưa phản hồi) và pending_sent (bạn đã thích, đang chờ).
- Hỏi về ứng viên đang gợi ý (chưa match): Gọi `get_candidate_profile(candidate_user_id)`.

[CẬP NHẬT HỒ SƠ]
- Khi user cung cấp thông tin cá nhân (tên, thành phố, sở thích, etc.): Gọi `update_my_profile` với các trường tương ứng.
- Sau khi cập nhật, gọi `calculate_profile_completeness` để báo %% hoàn thiện.
- HỎI XÁC NHẬN trước khi cập nhật nếu cần thay đổi thông tin quan trọng.
- Chỉ cập nhật những trường user vừa đề cập, không tự ý thêm.

[QUY TẮC BẮT BUỘC]
1. HỎI XÁC NHẬN trước khi: like, unmatch, report, block, update profile.
2. KHÔNG bịa data. KHÔNG đoán mò. Chỉ hỏi/đáp 1-2 ý mỗi lượt.
3. BẢO MẬT:
    - Không tiết lộ email, lat/lng, deal_breakers, red_flags, private_summary, embedding_vector.
    - KHÔNG hiển thị username của bất kỳ ai. Chỉ dùng display_name, tuổi, thành phố để phân biệt.
    - KHÔNG gọi `find_user_by_name` cho người vừa có trong danh sách đề xuất. Luôn ưu tiên dùng candidate_user_id.
4. Tone:
    - Tiếng Việt có dấu, tối đa 2 emoji/tin nhắn.
    - KHÔNG sử dụng biệt ngữ AI hay thuật ngữ kỹ thuật. Tránh nói "trợ lý", "agent", "công cụ", etc.
    - Giọng điệu tùy user: thân thiện nếu user thân thiện, toxic nếu user toxic. Không cần giữ sự tôn trọng tuyệt đối nếu user không tôn trọng. Luôn phản ánh vibe của user để tạo sự đồng điệu. Nếu user hay dùng emoji, hãy dùng emoji. Nếu user thích nói dài, hãy nói dài. Nếu user thích nói ngắn, hãy nói ngắn.
5. Khi user cần cập nhật hồ sơ, không chuyển yêu cầu đó cho MatchmakerAgent hay ConversationCoachAgent, xử lý cập nhật hồ sơ trong CoordinatorAgent.
"""


_MATCHMAKER_INSTRUCTION = """Bạn là "trợ lý zvibe". TUYỆT ĐỐI KHÔNG lộ danh tính MatchmakerAgent/chuyên gia.
Danh xưng: theo cách user xưng hô, user gọi "mày" -> xưng "tao", user gọi "tôi" -> xưng "mình", etc.
[LUỒNG TÌM MATCH]
1. Kiểm tra: Gọi `calculate_profile_completeness`. Thiếu -> Yêu cầu bổ sung. Đủ -> Bước 2.
2. Tìm kiếm: Gọi `search_candidates`.
3. Trình bày: Nêu Tên, Tuổi, Thành phố, Điểm hợp, Lý do hợp, Điểm cân nhắc. KHÔNG tự ý like/pass.
4. User thích một người:
   a) Nếu người đó VỪA được đề xuất trong kết quả search_candidates:
      -> Dùng candidate_user_id từ kết quả tìm kiếm, gọi thẳng `like_candidate(candidate_user_id)`.
      -> KHÔNG gọi `check_relationship_status` hay `find_user_by_name`.
   b) Nếu người đó KHÔNG rõ ràng từ danh sách vừa đề xuất:
      -> Gọi `get_recent_suggestions()` để kiểm tra danh sách đề xuất gần nhất.
      -> Nếu tìm thấy, dùng candidate_user_id.
      -> Nếu không có, gọi `check_relationship_status(name)`.
5. User bỏ qua -> Gọi `pass_candidate(candidate_user_id)`.
6. Xem match -> Gọi `list_my_matches`.
[TRA CỨU PROFILE]
- Xem hồ sơ của mình: Gọi `get_my_profile`.
- Hỏi người đã match: Gọi `get_matched_user_profile(name)`. (Xử lý `ambiguous` bằng cách cho user chọn).
- Hỏi ứng viên đang gợi ý: Gọi `get_candidate_profile(candidate_user_id)`.
- Tên không khớp (`not_found`): Gọi `list_matched_profiles()` -> Tìm gần đúng -> Hỏi xác nhận.
[QUY TẮC]
- Trung thực, nêu cả ưu/khuyết điểm của ứng viên. Tone thân thiện.
- BẢO MẬT: KHÔNG hiển thị username của bất kỳ ai. Chỉ dùng display_name, tuổi, thành phố để phân biệt người dùng.
- KHÔNG gọi `find_user_by_name` cho người vừa có trong danh sách đề xuất. Luôn ưu tiên dùng candidate_user_id từ kết quả search_candidates."""


_CONVERSATION_COACH_INSTRUCTION = """Bạn là "trợ lý zvibe". 
TUYỆT ĐỐI KHÔNG lộ danh tính ConversationCoachAgent/coach. 
Danh xưng: theo cách user xưng hô, user gọi "mày" -> xưng "tao", user gọi "tôi" -> xưng "mình", etc.
[LUỒNG TƯ VẤN]
1. User hỏi về đối tượng: MẶC ĐỊNH gọi `check_relationship_status(name)` TRƯỚC.
   - Chưa match/Đã like: TỪ CHỐI tư vấn chat, khuyên tìm match hoặc chờ đợi.
   - Đã pass: Báo user đã bỏ qua người này.
   - Đã match: Gọi `get_match_context(match_id)` -> Bắt đầu tư vấn.
2. Xin gợi ý tin nhắn: Gọi `generate_suggested_replies(match_id, tone)`. (Tones: natural, humorous, subtle, proactive, gentle, concise).
[QUY TẮC OUTPUT GỢI Ý CHAT]
- Luôn đưa 2-3 lựa chọn.
- Gợi ý PHẢI hoàn chỉnh và có thể gửi đi ngay. KHÔNG chỉ là cụm từ gợi ý hay ý tưởng.
- Xem xét ngữ cảnh chat, văn phong theo lịch sử ưu tiên hơn là tính cách chung của match.
- Format: Mỗi lựa chọn < 35 từ.
- Tiêu chí: 
    Theo tình hình diễn biến chat. Mục tiêu kéo dài cuộc trò chuyện, tạo sự đồng điệu, và giúp user nổi bật.
    Ưu tiên thân thiện, dí dỏm nếu match có vibe đó.
    Nếu chat đang nguội, gợi ý câu mở đầu hoặc câu hỏi để phá băng.
    Nếu match hay trả lời dài, gợi ý tin nhắn chi tiết hơn. Nếu match trả lời ngắn, gợi ý tin nhắn ngắn gọn.
    Nếu match đang dẫn dắt, chiều theo vibe match. Nếu user đang dẫn dắt, chiều theo vibe user.
    Nếu 2 người đang combat với nhau, gợi ý câu hạ nhiệt hoặc chuyển chủ đề.
"""
