"""
Tests for structured JSON logging configuration.

Tests logging_config.py module functionality.
"""

import json
import logging
from io import StringIO

import pytest

from src.logging_config import JSONFormatter, setup_logging


class TestJSONFormatter:
    """Test JSONFormatter class."""

    def test_basic_log_formatting(self):
        """Test that basic log record is formatted as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "test_module"
        assert log_data["function"] == "test_function"
        assert log_data["line"] == 42
        assert "timestamp" in log_data
        assert log_data["timestamp"].endswith("Z")

    def test_log_with_correlation_id(self):
        """Test that correlation_id is included if present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.correlation_id = "test-correlation-123"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["correlation_id"] == "test-correlation-123"

    def test_log_with_deployment_id(self):
        """Test that deployment_id is included if present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.deployment_id = "deploy-456"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["deployment_id"] == "deploy-456"

    def test_log_with_agent_id(self):
        """Test that agent_id is included if present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.agent_id = "agent-789"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["agent_id"] == "agent-789"

    def test_log_with_exception(self):
        """Test that exception info is included."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.module = "test_module"
        record.funcName = "test_function"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]
        assert "Test error" in log_data["exception"]


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_default(self, caplog):
        """Test that setup_logging configures root logger."""
        setup_logging(level="INFO")

        # Verify root logger has correct level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Verify at least one handler exists
        assert len(root_logger.handlers) > 0

        # Verify handler uses JSONFormatter
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_custom_level(self):
        """Test that custom log level is applied."""
        setup_logging(level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_noisy_libraries_silenced(self):
        """Test that noisy libraries have WARNING level."""
        setup_logging(level="INFO")

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert logging.getLogger("asyncpg").level == logging.WARNING
        assert logging.getLogger("sqlmodel").level == logging.WARNING

    def test_logging_produces_json(self, capfd):
        """Test that actual logging produces JSON output."""
        setup_logging(level="INFO")

        logger = logging.getLogger("test_logger")
        logger.info("Test JSON output", extra={"correlation_id": "test-123"})

        # Capture stdout
        captured = capfd.readouterr()

        # Parse JSON (get last line, as setup_logging also logs)
        lines = captured.out.strip().split("\n")
        log_data = json.loads(lines[-1])

        assert log_data["message"] == "Test JSON output"
        assert log_data["correlation_id"] == "test-123"
