import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class DatingGoal(str, enum.Enum):
    SERIOUS = "serious"
    CASUAL = "casual"
    FRIENDS_FIRST = "friends_first"
    NOT_SURE = "not_sure"


class VisibilityStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    HIDDEN = "hidden"


class LikeStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class MatchStatus(str, enum.Enum):
    ACTIVE = "active"
    UNMATCHED = "unmatched"
    BLOCKED = "blocked"


class RecommendationStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    LIKED = "liked"
    PASSED = "passed"
    EXPIRED = "expired"


class ScoreTier(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"


class AssistantRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class MemoryType(str, enum.Enum):
    PROFILE_FACT = "profile_fact"
    PREFERENCE = "preference"
    CONVERSATION_SUMMARY = "conversation_summary"
    SAFETY_NOTE = "safety_note"


class MediaPurpose(str, enum.Enum):
    AVATAR = "avatar"
    CHAT_ATTACHMENT = "chat_attachment"


class ReportCategory(str, enum.Enum):
    HARASSMENT = "harassment"
    SCAM = "scam"
    FAKE_PROFILE = "fake_profile"
    SEXUAL_MISCONDUCT = "sexual_misconduct"
    HATE_SPEECH = "hate_speech"
    THREATS = "threats"
    UNDERAGE = "underage"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class NotificationType(str, enum.Enum):
    LIKE_RECEIVED = "like_received"
    MATCH_CREATED = "match_created"
    MESSAGE_RECEIVED = "message_received"
    MATCH_UNAVAILABLE = "match_unavailable"
    SYSTEM = "system"


class ActionType(str, enum.Enum):
    CANDIDATE_CARDS = "candidate_cards"
    PROFILE_SUMMARY_CARD = "profile_summary_card"
    CONFIRMATION_REQUEST = "confirmation_request"
    MATCH_CELEBRATION = "match_celebration"
    SYSTEM_NOTICE = "system_notice"
    QUICK_ACTIONS = "quick_actions"


class AccountSource(str, enum.Enum):
    HUMAN = "human"
    SEED = "seed"
