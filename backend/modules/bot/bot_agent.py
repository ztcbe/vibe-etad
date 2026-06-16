"""BotAgent — auto-reply generation for demo/seed bot users.

Uses direct litellm call with system prompt built from bot profile and
match context. Simpler and more reliable than ADK agent for this use case
since bot replies are single-turn text generation without tool chaining.

The ADK agent builder (build_bot_agent) is kept for potential future use
where multi-turn agent behavior is needed.
"""
import logging
import uuid

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai.types import GenerateContentConfig

from app.config import settings
from modules.assistant.llm_adapter import build_llm
from modules.bot.tools import get_my_bot_profile, get_bot_match_context

logger = logging.getLogger(__name__)


# ── Bot Agent Builder (ADK — kept for future extension) ──────────────


def build_bot_agent() -> LlmAgent:
    """Build the BotAgent for autonomous demo account reply generation.

    This agent is invoked programmatically (not via user chat).
    It generates natural-sounding Vietnamese replies based on the bot's
    profile persona and chat context.
    """
    cfg = settings.bot_llm()
    return LlmAgent(
        name="BotAgent",
        description=(
            "Bot tự động cho tài khoản demo — tự động trả lời tin nhắn "
            "dựa trên hồ sơ cá nhân của bot."
        ),
        model=build_llm(
            model=cfg["model"],
            api_key=cfg["api_key"],
            api_base=cfg["api_base"],
            max_tokens=cfg["max_tokens"],
        ),
        instruction=_BOT_INSTRUCTION,
        tools=[
            FunctionTool(get_my_bot_profile),
            FunctionTool(get_bot_match_context),
        ],
        generate_content_config=GenerateContentConfig(
            temperature=settings.BOT_TEMPERATURE,
            max_output_tokens=settings.BOT_MAX_OUTPUT_TOKENS,
        ),
    )


# ── Reply Generation (invoked by event handler) ───────────────────────


async def generate_bot_reply(
    db, bot_user_id: uuid.UUID, match_id: uuid.UUID,
) -> str | None:
    """Generate an auto-reply using direct litellm call.

    Builds the system prompt from bot profile and match context,
    then calls the LLM directly. This is simpler and more reliable
    than ADK agent for single-turn text generation.
    """
    from modules.bot.context import get_match_context_for_bot
    from sqlalchemy import select
    from db.models.profile import UserProfile

    # Get match context
    ctx = await get_match_context_for_bot(db, bot_user_id, match_id)
    if "error" in ctx:
        logger.warning(f"Bot reply skipped: {ctx['error']}")
        return None

    chat_history = ctx.get("chat_history", [])
    other_user = ctx.get("other_user", {})

    # Don't reply if there are no messages
    if not chat_history:
        return None

    # Get bot's own profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == bot_user_id)
    )
    bot_profile_row = profile_result.scalar_one_or_none()
    if not bot_profile_row:
        logger.warning(f"Bot profile not found for user {bot_user_id}")
        return None

    bot_profile = {
        "display_name": bot_profile_row.display_name,
        "gender": bot_profile_row.gender,
        "dating_goal": bot_profile_row.dating_goal.value if bot_profile_row.dating_goal else None,
        "city": bot_profile_row.city,
        "personality_traits": bot_profile_row.personality_traits or [],
        "hobbies": bot_profile_row.hobbies or [],
        "communication_style": bot_profile_row.communication_style,
        "bio": bot_profile_row.bio,
    }

    system_prompt = build_bot_system_prompt(bot_profile, other_user)

    # Build messages: system + chat history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        role = "assistant" if str(msg["sender_user_id"]) == str(bot_user_id) else "user"
        messages.append({"role": role, "content": msg["content"]})

    # LLM call — use bot_llm() resolver like other agents
    cfg = settings.bot_llm()

    try:
        import litellm
        # Note: do NOT pass max_tokens or max_completion_tokens here.
        # Qwen thinking models consume token budget for internal reasoning;
        # low limits (e.g. 250) cause empty responses (finish_reason=length).
        # The system prompt instructs 1-3 sentences, which keeps output short.
        response = await litellm.acompletion(
            model=f"openai/{cfg['model']}",
            messages=messages,
            api_key=cfg["api_key"],
            api_base=cfg["api_base"],
            temperature=settings.BOT_TEMPERATURE,
        )
        raw = response.choices[0].message.content
        if raw:
            reply = raw.strip()
            reply = _strip_thinking(reply)
            if not reply:
                logger.warning(
                    f"Bot {bot_user_id} reply stripped to empty. "
                    f"Raw was {len(raw)} chars."
                )
        else:
            reply = None
            logger.warning(
                f"Bot {bot_user_id} LLM returned empty content for match {match_id}"
            )
        return reply or None
    except Exception:
        logger.exception("Bot LLM call failed for bot=%s match=%s", bot_user_id, match_id)
        return None


# ── System Prompt Builder ─────────────────────────────────────────────


def build_bot_system_prompt(bot_profile: dict, other_user: dict) -> str:
    """Build the bot's system prompt from its profile and the other user's info."""
    return BOT_SYSTEM_PROMPT_TEMPLATE.format(
        display_name=bot_profile.get("display_name", "ai đó"),
        gender=bot_profile.get("gender", "không xác định"),
        dating_goal=_vi_dating_goal(bot_profile.get("dating_goal")),
        city=bot_profile.get("city", "Việt Nam"),
        personality_traits=_format_list(bot_profile.get("personality_traits")),
        hobbies=_format_list(bot_profile.get("hobbies")),
        communication_style=bot_profile.get("communication_style", "thân thiện"),
        bio=bot_profile.get("bio", ""),
        other_display_name=other_user.get("display_name", "ai đó"),
        other_age=str(other_user.get("age") or "?"),
        other_city=other_user.get("city", "Việt Nam"),
    )


BOT_SYSTEM_PROMPT_TEMPLATE = """Bạn là {display_name}, một người dùng trên ứng dụng hẹn hò zvibe.

Hồ sơ của bạn:
- Giới tính: {gender}
- Mục tiêu hẹn hò: {dating_goal}
- Thành phố: {city}
- Tính cách: {personality_traits}
- Sở thích: {hobbies}
- Phong cách giao tiếp: {communication_style}
- Bio: {bio}

Bạn đang trò chuyện 1-1 với người đã match với bạn qua ứng dụng.
Người đang nói chuyện với bạn tên là {other_display_name}, {other_age} tuổi, đến từ {other_city}.

QUY TẮC QUAN TRỌNG:
- Luôn trả lời bằng tiếng Việt có dấu
- Ngắn gọn, tự nhiên, tùy ngữ cảnh hiện tại, không quá 35 từ.
- Đúng với vibe và tính cách trong hồ sơ của bạn
- Tuyệt đối KHÔNG để lộ rằng bạn là bot/AI/trợ lý
- KHÔNG dùng biệt ngữ AI hay thuật ngữ kỹ thuật
- Phản hồi dựa trên nội dung tin nhắn gần nhất, tham khảo lịch sử chat nếu cần
- Nếu được hỏi về sở thích/công việc, trả lời dựa trên hồ sơ của bạn
- Từ chối khéo nếu bị hỏi về những chủ đề không phù hợp
"""


# ── Agent Instruction (for ADK agent, kept for reference) ─────────────


_BOT_INSTRUCTION = """Bạn là bot tự động cho tài khoản demo trên ứng dụng hẹn hò zvibe.

NHIỆM VỤ: Khi nhận được tin nhắn mới trong cuộc trò chuyện, hãy trả lời một cách tự nhiên dựa trên hồ sơ cá nhân của bạn.

LUỒNG XỬ LÝ:
1. Gọi `get_my_bot_profile()` để lấy hồ sơ của bạn (tên, giới tính, tính cách, sở thích, phong cách giao tiếp, bio...).
2. Gọi `get_bot_match_context(match_id)` để lấy lịch sử chat và thông tin người đang nói chuyện với bạn.
3. Dựa vào hồ sơ của bạn + ngữ cảnh chat + tin nhắn gần nhất, soạn một câu trả lời ngắn gọn, tự nhiên.

QUY TẮC BẮT BUỘC:
- Luôn trả lời bằng tiếng Việt có dấu
- Ngắn gọn, tự nhiên, tùy ngữ cảnh hiện tại, không quá 35 từ.
- Đúng với tính cách và sở thích trong hồ sơ của bạn
- TUYỆT ĐỐI KHÔNG để lộ rằng bạn là bot/AI/trợ lý
- KHÔNG dùng biệt ngữ AI hay thuật ngữ kỹ thuật
- Phản hồi dựa trên nội dung tin nhắn gần nhất, tham khảo lịch sử chat nếu cần
- Nếu được hỏi về sở thích/công việc, trả lời dựa trên hồ sơ của bạn
- Từ chối khéo nếu bị hỏi về những chủ đề không phù hợp
"""


# ── Helpers ────────────────────────────────────────────────────────────


def _strip_thinking(text: str) -> str:
    """Remove thinking/reasoning XML tags from model output, keep content.

    Some models (Qwen, DeepSeek) wrap output in <think> tags. Instead of
    removing the entire block (which would lose the reply if it's inside),
    we only strip the tags themselves and keep the content.
    """
    import re
    # First try: extract content after the last closing think tag
    # (the actual reply often comes after the reasoning)
    parts = re.split(r'</think[^>]*>', text, flags=re.DOTALL)
    if len(parts) > 1 and parts[-1].strip():
        return parts[-1].strip()

    # Fallback: just remove the XML tags, keeping content
    text = re.sub(r'</?think[^>]*>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?thinking[^>]*>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?thought[^>]*>', '', text, flags=re.DOTALL)
    return text.strip()


def _vi_dating_goal(goal: str | None) -> str:
    """Translate dating goal enum value to Vietnamese."""
    mapping = {
        "serious": "nghiêm túc",
        "casual": "tình cảm thoải mái",
        "friends_first": "làm bạn trước",
        "not_sure": "đang tìm hiểu",
    }
    return mapping.get(goal or "", "đang tìm hiểu")


def _format_list(items) -> str:
    """Format a list into a Vietnamese comma-separated string."""
    if not items:
        return "chưa có"
    if isinstance(items, list):
        return ", ".join(str(i) for i in items)
    return str(items)
