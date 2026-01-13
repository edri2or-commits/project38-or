"""
Structured JSON logging configuration for production observability.

Implements structured logging with correlation IDs for request tracing.
Based on Day 6 of implementation-roadmap.md.
"""

import json
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON with ISO 8601 timestamps and correlation IDs.

    Example:
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(JSONFormatter())
        >>> logger = logging.getLogger(__name__)
        >>> logger.addHandler(handler)
        >>> logger.info("Deployment started", extra={"correlation_id": "deploy-123"})
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Python logging.LogRecord

        Returns:
            JSON string with structured log data
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation_id if present (for request tracing)
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Add deployment_id if present (for deployment tracking)
        if hasattr(record, "deployment_id"):
            log_entry["deployment_id"] = record.deployment_id

        # Add agent_id if present (for agent tracking)
        if hasattr(record, "agent_id"):
            log_entry["agent_id"] = record.agent_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(level: str = "INFO"):
    """
    Configure structured JSON logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> setup_logging(level="INFO")
        >>> logging.info("Application started")
    """
    # Create JSON formatter
    formatter = JSONFormatter()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add console handler
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("sqlmodel").setLevel(logging.WARNING)

    logging.info("Structured JSON logging configured", extra={"log_level": level})
