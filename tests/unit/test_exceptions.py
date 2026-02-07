"""Tests for custom exception hierarchy."""

import pytest

from common.exceptions import (
    AccessDeniedError,
    ManifestError,
    NonRetryableError,
    ObjectTooLargeError,
    RetryableError,
    TransferError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_transfer_error_is_base(self):
        err = TransferError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"
        assert err.details == {}

    def test_transfer_error_with_details(self):
        err = TransferError("test", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_retryable_is_transfer_error(self):
        err = RetryableError("throttled")
        assert isinstance(err, TransferError)

    def test_non_retryable_is_transfer_error(self):
        err = NonRetryableError("bad config")
        assert isinstance(err, TransferError)

    def test_access_denied_is_non_retryable(self):
        err = AccessDeniedError("forbidden")
        assert isinstance(err, NonRetryableError)
        assert isinstance(err, TransferError)

    def test_object_too_large_is_non_retryable(self):
        err = ObjectTooLargeError("too big")
        assert isinstance(err, NonRetryableError)

    def test_manifest_error_is_non_retryable(self):
        err = ManifestError("bad manifest")
        assert isinstance(err, NonRetryableError)

    def test_validation_error_is_non_retryable(self):
        err = ValidationError("mismatch")
        assert isinstance(err, NonRetryableError)
