from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # LLM defaults (used when per-agent config is not set)
    LLM_BASE_URL: str = "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "google/gemma-4-31b-it"
    LLM_MAX_TOKENS: int = 256000

    # CoordinatorAgent — entry point, general chat, routing
    COORDINATOR_LLM_MODEL: str | None = None
    COORDINATOR_LLM_API_KEY: str | None = None
    COORDINATOR_LLM_BASE_URL: str | None = None
    COORDINATOR_LLM_MAX_TOKENS: int | None = None
    COORDINATOR_TEMPERATURE: float = 0.8
    COORDINATOR_MAX_OUTPUT_TOKENS: int = 1500

    # MatchmakerAgent — profile analysis, candidate search, like/pass
    MATCHMAKER_LLM_MODEL: str | None = None
    MATCHMAKER_LLM_API_KEY: str | None = None
    MATCHMAKER_LLM_BASE_URL: str | None = None
    MATCHMAKER_LLM_MAX_TOKENS: int | None = None
    MATCHMAKER_TEMPERATURE: float = 0.7
    MATCHMAKER_MAX_OUTPUT_TOKENS: int = 1500

    # ConversationCoachAgent — reply suggestions, tone-aware generation
    COACH_LLM_MODEL: str | None = None
    COACH_LLM_API_KEY: str | None = None
    COACH_LLM_BASE_URL: str | None = None
    COACH_LLM_MAX_TOKENS: int | None = None
    COACH_TEMPERATURE: float = 0.9
    COACH_MAX_OUTPUT_TOKENS: int = 1000

    # Bot agent — auto-reply for demo bot users
    BOT_LLM_MODEL: str | None = None
    BOT_LLM_API_KEY: str | None = None
    BOT_LLM_BASE_URL: str | None = None
    BOT_LLM_MAX_TOKENS: int | None = None
    BOT_TEMPERATURE: float = 0.9
    BOT_MAX_OUTPUT_TOKENS: int = 250
    BOT_REPLY_DELAY_MIN: float = 2.0
    BOT_REPLY_DELAY_MAX: float = 8.0

    # Media
    MEDIA_UPLOAD_DIR: str = "./uploads"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # App
    APP_ENV: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Per-agent LLM config resolvers ──

    def coordinator_llm(self) -> dict:
        return {
            "model": self.COORDINATOR_LLM_MODEL or self.LLM_MODEL,
            "api_key": self.COORDINATOR_LLM_API_KEY or self.LLM_API_KEY,
            "api_base": self.COORDINATOR_LLM_BASE_URL or self.LLM_BASE_URL,
            "max_tokens": self.COORDINATOR_LLM_MAX_TOKENS or self.LLM_MAX_TOKENS,
        }

    def matchmaker_llm(self) -> dict:
        return {
            "model": self.MATCHMAKER_LLM_MODEL or self.LLM_MODEL,
            "api_key": self.MATCHMAKER_LLM_API_KEY or self.LLM_API_KEY,
            "api_base": self.MATCHMAKER_LLM_BASE_URL or self.LLM_BASE_URL,
            "max_tokens": self.MATCHMAKER_LLM_MAX_TOKENS or self.LLM_MAX_TOKENS,
        }

    def coach_llm(self) -> dict:
        return {
            "model": self.COACH_LLM_MODEL or self.LLM_MODEL,
            "api_key": self.COACH_LLM_API_KEY or self.LLM_API_KEY,
            "api_base": self.COACH_LLM_BASE_URL or self.LLM_BASE_URL,
            "max_tokens": self.COACH_LLM_MAX_TOKENS or self.LLM_MAX_TOKENS,
        }

    def bot_llm(self) -> dict:
        return {
            "model": self.BOT_LLM_MODEL or self.LLM_MODEL,
            "api_key": self.BOT_LLM_API_KEY or self.LLM_API_KEY,
            "api_base": self.BOT_LLM_BASE_URL or self.LLM_BASE_URL,
            "max_tokens": self.BOT_LLM_MAX_TOKENS or self.LLM_MAX_TOKENS,
        }


settings = Settings()
