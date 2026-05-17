from __future__ import annotations

import logging
from pathlib import Path

from .database import default_logs_dir

LOGS_DIR = default_logs_dir()
LOG_PATH = LOGS_DIR / "app.log"


def current_log_path() -> Path:
    return default_logs_dir() / "app.log"


def configure_logging() -> None:
    log_path = current_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if any(getattr(handler, "baseFilename", None) == str(log_path) for handler in root_logger.handlers):
        return

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
