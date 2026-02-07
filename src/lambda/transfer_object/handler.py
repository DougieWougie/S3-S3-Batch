"""TransferObject Lambda: assumes dest role, server-side copy with KMS re-encryption."""

import logging

from common.config import TransferConfig
from common.exceptions import NonRetryableError
from common.logger import get_logger, log_with_context
from common.s3_client import copy_object, multipart_copy
from common.sts_client import assume_role, get_boto3_client

logger = get_logger(__name__)


def handler(event: dict, context) -> dict:
    """Copy a single object from source to destination bucket.

    Input event (from Distributed Map):
        {
            "Key": "path/to/object.txt",
            "Size": 12345,
            "ETag": "\"abc123\"",
            "source_bucket": "...",
            "destination_bucket": "...",
            "destination_prefix": "...",
            "execution_id": "..."
        }

    Returns:
        {
            "status": "SUCCESS",
            "source_key": "...",
            "dest_key": "...",
            "size": 12345,
        }
    """
    request_id = getattr(context, "aws_request_id", "local")
    config = TransferConfig.from_env()

    source_key = event["Key"]
    object_size = event["Size"]
    source_bucket = event.get("source_bucket", config.source_bucket)
    dest_bucket = event.get("destination_bucket", config.destination_bucket)
    dest_prefix = event.get("destination_prefix", config.destination_prefix)
    execution_id = event.get("execution_id", "unknown")

    # Compute destination key: replace source prefix with destination prefix
    source_prefix = event.get("source_prefix", config.source_prefix)
    if source_prefix and source_key.startswith(source_prefix):
        relative_key = source_key[len(source_prefix):]
    else:
        relative_key = source_key

    dest_key = f"{dest_prefix}{relative_key}" if dest_prefix else relative_key

    log_with_context(
        logger,
        logging.INFO,
        "TransferObject started",
        request_id=request_id,
        source_key=source_key,
        dest_key=dest_key,
        size=object_size,
        execution_id=execution_id,
    )

    # Assume destination role (which has read on source via bucket policy + KMS grant)
    credentials = assume_role(
        role_arn=config.destination_role_arn,
        session_name=f"Transfer-{execution_id[:8]}",
        external_id=config.external_id,
    )
    dest_s3 = get_boto3_client("s3", credentials)

    try:
        if object_size < config.multipart_threshold_bytes:
            copy_object(
                s3_client=dest_s3,
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
                kms_key_id=config.destination_kms_key_id,
            )
        else:
            multipart_copy(
                s3_client=dest_s3,
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
                object_size=object_size,
                kms_key_id=config.destination_kms_key_id,
                part_size=config.multipart_chunk_size_bytes,
            )
    except Exception as e:
        log_with_context(
            logger,
            logging.ERROR,
            "TransferObject failed",
            request_id=request_id,
            source_key=source_key,
            dest_key=dest_key,
            error=str(e),
        )
        raise

    log_with_context(
        logger,
        logging.INFO,
        "TransferObject complete",
        request_id=request_id,
        source_key=source_key,
        dest_key=dest_key,
        size=object_size,
    )

    return {
        "status": "SUCCESS",
        "source_key": source_key,
        "dest_key": dest_key,
        "size": object_size,
    }
