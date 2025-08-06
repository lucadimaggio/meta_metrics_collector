import logging
import os
import json
from functools import wraps
from datetime import datetime

# Attempt to use RichHandler for pretty console output if available
try:
    from rich.logging import RichHandler
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs logs in JSON format.
    """
    def format(self, record: logging.LogRecord) -> str:
        record_dict = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            record_dict["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(record_dict)


def get_logger(name: str) -> logging.Logger:
    """
    Factory for creating a configured logger.

    Reads environment variables:
    - LOG_LEVEL: logging level (default: INFO)
    - LOG_JSON: if true, emits JSON-formatted logs
    """
    # Determine log level
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    # Validate level_name
    if level_name not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level_name = "INFO"
    level = getattr(logging, level_name)
    json_output = os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes", "y")

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        # Console handler
        if _RICH_AVAILABLE:
            console_handler = RichHandler(rich_tracebacks=True)
        else:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter("%(levelname)s | %(asctime)s | %(name)s | %(message)s")
            )
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

        if json_output:
            json_handler = logging.StreamHandler()
            json_handler.setLevel(level)
            json_handler.setFormatter(JsonFormatter())
            logger.addHandler(json_handler)

    return logger


def log_exceptions(func):
    """
    Decorator to log unhandled exceptions with full traceback, then re-raise.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"Unhandled exception in {func.__qualname__}")
            raise
    return wrapper


def log_step_start(step_number: int, description: str):
    """
    Helper to log the start of a processing step.
    """
    logger = get_logger(f"step_{step_number}")
    logger.info(f"🚀 Avvio Step {step_number}: {description}")

# Initialize root logger and emit test logs
_root_logger = get_logger("root")
_root_logger.info("Centralized logger initialized at INFO level")
_root_logger.debug("Centralized logger DEBUG test: debug-level logs will appear if LOG_LEVEL=DEBUG")
