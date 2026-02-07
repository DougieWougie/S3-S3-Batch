"""Tests for structured JSON logging."""

import json
import logging

import pytest

from common.logger import JSONFormatter, get_logger, log_with_context


class TestJSONFormatter:
    def test_basic_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "test message"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed

    def test_format_with_extra_data(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="with extras",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"key1": "value1", "key2": 42}
        record.request_id = "req-123"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["key1"] == "value1"
        assert parsed["key2"] == 42
        assert parsed["request_id"] == "req-123"

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test_module")
        assert logger.name == "test_module"
        assert len(logger.handlers) == 1

    def test_idempotent(self):
        logger1 = get_logger("idempotent_test")
        logger2 = get_logger("idempotent_test")
        assert logger1 is logger2
        assert len(logger1.handlers) == 1


class TestLogWithContext:
    def test_log_with_context(self, capfd):
        logger = get_logger("context_test")
        log_with_context(
            logger,
            logging.INFO,
            "test message",
            request_id="req-456",
            operation="copy",
            count=5,
        )
        output = capfd.readouterr().out
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["request_id"] == "req-456"
        assert parsed["operation"] == "copy"
        assert parsed["count"] == 5
