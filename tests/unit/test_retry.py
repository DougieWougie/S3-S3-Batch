"""Tests for exponential backoff with jitter decorator."""

from unittest.mock import patch

import pytest

from common.exceptions import NonRetryableError, RetryableError
from common.retry import exponential_backoff_with_jitter


class TestExponentialBackoffWithJitter:
    def test_success_on_first_attempt(self):
        @exponential_backoff_with_jitter(max_attempts=3)
        def succeed():
            return "ok"

        assert succeed() == "ok"

    @patch("common.retry.time.sleep")
    def test_retries_on_retryable_error(self, mock_sleep):
        call_count = 0

        @exponential_backoff_with_jitter(max_attempts=3, base_delay=1.0)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("transient")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    @patch("common.retry.time.sleep")
    def test_raises_after_max_attempts(self, mock_sleep):
        @exponential_backoff_with_jitter(max_attempts=3, base_delay=1.0)
        def always_fail():
            raise RetryableError("always fails")

        with pytest.raises(RetryableError, match="always fails"):
            always_fail()
        assert mock_sleep.call_count == 2

    def test_non_retryable_raises_immediately(self):
        call_count = 0

        @exponential_backoff_with_jitter(max_attempts=5)
        def access_denied():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("access denied")

        with pytest.raises(NonRetryableError, match="access denied"):
            access_denied()
        assert call_count == 1

    @patch("common.retry.time.sleep")
    @patch("common.retry.random.uniform")
    def test_jitter_calculation(self, mock_uniform, mock_sleep):
        mock_uniform.return_value = 0.5
        call_count = 0

        @exponential_backoff_with_jitter(
            max_attempts=3, base_delay=2.0, max_delay=10.0
        )
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("retry")
            return "ok"

        fail_then_succeed()
        # First retry: uniform(0, min(10, 2 * 2^0)) = uniform(0, 2)
        mock_uniform.assert_called_with(0, 2.0)

    @patch("common.retry.time.sleep")
    def test_custom_retryable_exceptions(self, mock_sleep):
        call_count = 0

        @exponential_backoff_with_jitter(
            max_attempts=3,
            retryable_exceptions=(ValueError,),
        )
        def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("custom error")
            return "ok"

        result = fail_with_value_error()
        assert result == "ok"
        assert call_count == 2
