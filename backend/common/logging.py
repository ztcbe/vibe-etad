import logging
import sys

from app.config import settings


def setup_logging():
    level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
