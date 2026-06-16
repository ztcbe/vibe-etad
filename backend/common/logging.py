import logging
import sys

from app.config import settings


def setup_logging():
    """Configure application-wide logging.

    App loggers use the level set by APP_ENV (DEBUG for development, INFO for production).
    Noisy third-party loggers (litellm, google.adk, sqlalchemy) are clamped to WARNING
    to avoid flooding stdout with internal debug traces.
    """
    level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # ── Silence noisy third-party loggers ──────────────────────────────
    _SILENCED = [
        "litellm",
        "httpx",
        "httpcore",
        "openai",
        "google.adk",
        "google.genai",
        "sqlalchemy.engine",
    ]
    for name in _SILENCED:
        logging.getLogger(name).setLevel(logging.WARNING)

    # ── Ensure app loggers aren't accidentally clamped ─────────────────
    for app_prefix in ("modules", "common", "db", "app"):
        logging.getLogger(app_prefix).setLevel(level)
