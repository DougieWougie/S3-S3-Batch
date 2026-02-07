"""Custom exception hierarchy for S3-to-S3 transfer operations."""


class TransferError(Exception):
    """Base exception for all transfer operations."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class RetryableError(TransferError):
    """Errors that should be retried (throttling, transient failures)."""
    pass


class NonRetryableError(TransferError):
    """Errors that should NOT be retried (access denied, invalid config)."""
    pass


class AccessDeniedError(NonRetryableError):
    """Cross-account access denied - check IAM roles and policies."""
    pass


class ObjectTooLargeError(NonRetryableError):
    """Object exceeds maximum supported size."""
    pass


class ManifestError(NonRetryableError):
    """Error reading or writing the transfer manifest."""
    pass


class ValidationError(NonRetryableError):
    """Transfer validation failed - count or integrity mismatch."""
    pass
