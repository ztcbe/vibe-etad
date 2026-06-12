from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # LLM (VNGCloud MaaS)
    LLM_BASE_URL: str = "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "google/gemma-4-31b-it"

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


settings = Settings()
