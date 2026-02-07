"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TransferConfig:
    """Transfer configuration from Lambda environment variables."""

    # Cross-account roles
    source_role_arn: str = ""
    destination_role_arn: str = ""
    external_id: str = ""

    # S3 buckets
    source_bucket: str = ""
    destination_bucket: str = ""
    source_prefix: str = ""
    destination_prefix: str = ""
    manifest_bucket: str = ""

    # KMS keys
    source_kms_key_id: str = ""
    destination_kms_key_id: str = ""

    # Transfer settings
    multipart_threshold_bytes: int = 5 * 1024 * 1024 * 1024  # 5 GB
    multipart_chunk_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    max_retry_attempts: int = 5
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0

    # Validation
    validation_sample_size: int = 10

    # Notifications
    sns_topic_arn: str = ""

    @classmethod
    def from_env(cls) -> "TransferConfig":
        """Load configuration from environment variables."""
        return cls(
            source_role_arn=os.environ.get("SOURCE_ROLE_ARN", ""),
            destination_role_arn=os.environ.get("DESTINATION_ROLE_ARN", ""),
            external_id=os.environ.get("EXTERNAL_ID", ""),
            source_bucket=os.environ.get("SOURCE_BUCKET", ""),
            destination_bucket=os.environ.get("DESTINATION_BUCKET", ""),
            source_prefix=os.environ.get("SOURCE_PREFIX", ""),
            destination_prefix=os.environ.get("DESTINATION_PREFIX", ""),
            manifest_bucket=os.environ.get("MANIFEST_BUCKET", ""),
            source_kms_key_id=os.environ.get("SOURCE_KMS_KEY_ID", ""),
            destination_kms_key_id=os.environ.get("DESTINATION_KMS_KEY_ID", ""),
            multipart_threshold_bytes=int(
                os.environ.get(
                    "MULTIPART_THRESHOLD_BYTES",
                    str(5 * 1024 * 1024 * 1024),
                )
            ),
            multipart_chunk_size_bytes=int(
                os.environ.get("MULTIPART_CHUNK_SIZE_BYTES", str(100 * 1024 * 1024))
            ),
            max_retry_attempts=int(os.environ.get("MAX_RETRY_ATTEMPTS", "5")),
            retry_base_delay=float(os.environ.get("RETRY_BASE_DELAY", "1.0")),
            retry_max_delay=float(os.environ.get("RETRY_MAX_DELAY", "60.0")),
            validation_sample_size=int(
                os.environ.get("VALIDATION_SAMPLE_SIZE", "10")
            ),
            sns_topic_arn=os.environ.get("SNS_TOPIC_ARN", ""),
        )
