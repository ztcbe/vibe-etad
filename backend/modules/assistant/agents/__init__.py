"""Agent builder — creates ADK agents with injected context and tools."""
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai.types import GenerateContentConfig

from modules.assistant.llm_adapter import VngCloudLlm
from modules.assistant.tools import profile_tools, matching_tools
from modules.assistant.prompts.zvibe_assistant import ZVIBE_ASSISTANT_SYSTEM_PROMPT
from modules.assistant.prompts.profile_builder import PROFILE_BUILDER_SYSTEM_PROMPT


def _build_llm() -> VngCloudLlm:
    return VngCloudLlm()


def build_zvibe_agent() -> LlmAgent:
    """Build the root ZvibeAssistantAgent.

    Agents:
    - ZvibeAssistantAgent (root): handles all user interactions
    - ProfileBuilderAgent (sub): onboarding and profile updates
    - MatchmakerAgent (sub): candidate search, like, pass, list matches
    """
    profile_builder = LlmAgent(
        name="ProfileBuilderAgent",
        description="Xây dựng và cập nhật dating profile cho người dùng mới.",
        model=_build_llm(),
        instruction=PROFILE_BUILDER_SYSTEM_PROMPT,
        tools=[
            FunctionTool(profile_tools.get_my_profile),
            FunctionTool(profile_tools.update_my_profile),
            FunctionTool(profile_tools.calculate_profile_completeness),
        ],
        generate_content_config=GenerateContentConfig(temperature=0.8, max_output_tokens=1500),
        disallow_transfer_to_parent=False,
    )

    matchmaker = LlmAgent(
        name="MatchmakerAgent",
        description="Tìm kiếm người phù hợp cho user. Dùng khi user muốn tìm match, xem danh sách match, hoặc like/pass.",
        model=_build_llm(),
        instruction="""Bạn là MatchmakerAgent của zvibe. Nhiệm vụ: tìm người phù hợp cho user.

Khi user muốn tìm match:
1. Gọi `calculate_profile_completeness` trước — nếu chưa đủ thông tin, báo user cần bổ sung.
2. Gọi `search_candidates` để lấy danh sách ứng viên.
3. Trình bày từng ứng viên với: tên, tuổi, thành phố, điểm hợp, lý do hợp, điểm cần cân nhắc.
4. KHÔNG tự ý like/pass nếu chưa có xác nhận rõ ràng từ user.
5. Nếu user nói "thích", "like", "match" → gọi `like_candidate` và thông báo kết quả.
6. Nếu user nói "bỏ qua", "pass", "không hợp" → gọi `pass_candidate`.

Luôn dùng tiếng Việt tự nhiên, có dấu. Tone thân thiện, ấm áp.""",
        tools=[
            FunctionTool(profile_tools.calculate_profile_completeness),
            FunctionTool(matching_tools.search_candidates),
            FunctionTool(matching_tools.like_candidate),
            FunctionTool(matching_tools.pass_candidate),
            FunctionTool(matching_tools.list_my_matches),
        ],
        generate_content_config=GenerateContentConfig(temperature=0.7, max_output_tokens=1500),
        disallow_transfer_to_parent=False,
    )

    root = LlmAgent(
        name="ZvibeAssistantAgent",
        description="Trợ lý hẹn hò zvibe — giúp người dùng tạo hồ sơ, tìm match, chat, và được tư vấn.",
        model=_build_llm(),
        instruction=ZVIBE_ASSISTANT_SYSTEM_PROMPT,
        tools=[
            FunctionTool(profile_tools.get_my_profile),
            FunctionTool(profile_tools.calculate_profile_completeness),
        ],
        sub_agents=[profile_builder, matchmaker],
        generate_content_config=GenerateContentConfig(temperature=0.8, max_output_tokens=1500),
        disallow_transfer_to_parent=False,
    )

    return root
