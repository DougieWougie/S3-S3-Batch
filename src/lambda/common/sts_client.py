"""STS role assumption with credential caching."""

import time
from typing import Any, Dict

import boto3

from common.exceptions import AccessDeniedError, RetryableError
from common.logger import get_logger
from common.retry import exponential_backoff_with_jitter

logger = get_logger(__name__)

# Module-level credential cache: {role_arn: {"credentials": ..., "expiry": ...}}
_credential_cache: Dict[str, Dict[str, Any]] = {}

# Refresh credentials 5 minutes before expiry
_CREDENTIAL_BUFFER_SECONDS = 300


def _is_cached_credential_valid(role_arn: str) -> bool:
    """Check if cached credentials are still valid."""
    if role_arn not in _credential_cache:
        return False
    expiry = _credential_cache[role_arn].get("expiry", 0)
    return time.time() < (expiry - _CREDENTIAL_BUFFER_SECONDS)


@exponential_backoff_with_jitter(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(RetryableError,),
)
def assume_role(
    role_arn: str,
    session_name: str = "S3TransferSession",
    external_id: str = "",
    duration_seconds: int = 3600,
) -> Dict[str, str]:
    """Assume an IAM role and return temporary credentials.

    Returns cached credentials if still valid.
    """
    if _is_cached_credential_valid(role_arn):
        logger.info("Using cached credentials for role %s", role_arn)
        return _credential_cache[role_arn]["credentials"]

    logger.info("Assuming role %s with session %s", role_arn, session_name)
    sts_client = boto3.client("sts")

    try:
        kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": duration_seconds,
        }
        if external_id:
            kwargs["ExternalId"] = external_id

        response = sts_client.assume_role(**kwargs)
        raw_creds = response["Credentials"]
        credentials = {
            "aws_access_key_id": raw_creds["AccessKeyId"],
            "aws_secret_access_key": raw_creds["SecretAccessKey"],
            "aws_session_token": raw_creds["SessionToken"],
        }

        _credential_cache[role_arn] = {
            "credentials": credentials,
            "expiry": raw_creds["Expiration"].timestamp(),
        }

        logger.info("Successfully assumed role %s", role_arn)
        return credentials

    except sts_client.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("AccessDenied", "AccessDeniedException"):
            raise AccessDeniedError(
                f"Access denied assuming role {role_arn}: {e}",
                details={"role_arn": role_arn, "error_code": error_code},
            ) from e
        raise RetryableError(
            f"STS error assuming role {role_arn}: {e}",
            details={"role_arn": role_arn, "error_code": error_code},
        ) from e


def get_boto3_client(service: str, credentials: Dict[str, str], region: str = ""):
    """Create a boto3 client with assumed role credentials."""
    kwargs = {
        "service_name": service,
        "aws_access_key_id": credentials["aws_access_key_id"],
        "aws_secret_access_key": credentials["aws_secret_access_key"],
        "aws_session_token": credentials["aws_session_token"],
    }
    if region:
        kwargs["region_name"] = region
    return boto3.client(**kwargs)


def clear_credential_cache() -> None:
    """Clear the credential cache (useful for testing)."""
    _credential_cache.clear()
