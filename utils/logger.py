import logging
import os
import json
from functools import wraps
from datetime import datetime

# RichHandler for enhanced console formatting, if available
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
        data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a singleton logger configured with environment settings.

    Environment variables:
      - LOG_LEVEL: one of DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
      - LOG_JSON: enable JSON output if true (default: false)
    """
    # Read and validate log level
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    if level_str not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level_str = "INFO"
    # Ensure minimum INFO level
    if getattr(logging, level_str) < logging.INFO:
        level_str = "INFO"
    level = getattr(logging, level_str)

    # Read JSON output flag
    json_flag = os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes", "y")

    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # prevent double logging

    # Configure handlers once
    if not logger.handlers:
        # Console Handler
        if _RICH_AVAILABLE:
            console = RichHandler(rich_tracebacks=True)
            console.setLevel(level)
            logger.info("Configuring RichHandler for console output")
            logger.addHandler(console)
            logger.debug("RichHandler enabled for console output")
        else:
            console = logging.StreamHandler()
            console.setLevel(level)
            fmt = logging.Formatter(
                "%(levelname)s | %(asctime)s | %(name)s | %(message)s"
            )
            console.setFormatter(fmt)
            logger.info("Configuring standard StreamHandler for console output")
            logger.addHandler(console)
            logger.debug("Standard StreamHandler enabled for console output")

        # JSON Handler
        if json_flag:
            json_handler = logging.StreamHandler()
            json_handler.setLevel(level)
            json_handler.setFormatter(JsonFormatter())
            logger.addHandler(json_handler)
            logger.debug("JsonFormatter enabled for JSON output")

        # Report configuration summary
        logger.info(f"Logger '{name}' initialized at level {level_str}")
        if json_flag:
            logger.info("JSON logging is enabled")

    return logger


def log_exceptions(func):
    """
    Decorator: logs any unhandled exceptions in the function, including traceback.
    Re-raises the original exception after logging.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"Exception in {func.__qualname__}")
            raise
    return wrapper


def log_step_start(step_number: int, description: str):
    """
    Logs the start of a processing step at INFO level.
    """
    name = f"step_{step_number}"
    logger = get_logger(name)
    message = f"🚀 Starting Step {step_number}: {description}"
    logger.info(message)

# Example: Initialize root logger configuration when this module is imported
if __name__ != '__main__':
    root_logger = get_logger('meta_metrics_collector')
    root_logger.info("Centralized logger module loaded for Meta Metrics Collector")

# Test logs: verificare che INFO e DEBUG siano emessi correttamente
root_logger.debug("TEST DEBUG: se vedi questo, LOG_LEVEL=DEBUG è attivo")
root_logger.info("TEST INFO: test di logging INFO configurato correttamente")

# FILE: utils/logger.py
