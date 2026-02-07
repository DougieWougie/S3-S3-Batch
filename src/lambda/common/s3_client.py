"""S3 client wrapper for paginated listing, copy, and multipart copy."""

import math
from typing import Any, Dict, Iterator, List

import boto3

from common.exceptions import (
    AccessDeniedError,
    ObjectTooLargeError,
    RetryableError,
)
from common.logger import get_logger
from common.retry import exponential_backoff_with_jitter

logger = get_logger(__name__)

# Max object size for S3 (5 TB)
MAX_OBJECT_SIZE = 5 * 1024 * 1024 * 1024 * 1024

# Threshold for server-side copy vs multipart copy (5 GB)
DEFAULT_MULTIPART_THRESHOLD = 5 * 1024 * 1024 * 1024

# Default part size for multipart copy (100 MB)
DEFAULT_PART_SIZE = 100 * 1024 * 1024


def _classify_s3_error(e, operation: str) -> Exception:
    """Classify a botocore ClientError into our exception hierarchy."""
    error_code = e.response["Error"]["Code"]
    message = f"S3 {operation} failed: {e}"
    details = {"error_code": error_code, "operation": operation}

    if error_code in ("AccessDenied", "403"):
        return AccessDeniedError(message, details=details)
    if error_code in ("SlowDown", "503", "RequestTimeout", "InternalError"):
        return RetryableError(message, details=details)
    return RetryableError(message, details=details)


@exponential_backoff_with_jitter(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    retryable_exceptions=(RetryableError,),
)
def list_objects_paginated(
    s3_client,
    bucket: str,
    prefix: str = "",
) -> Iterator[Dict[str, Any]]:
    """List all objects in a bucket/prefix using pagination.

    Yields dicts with: Key, Size, LastModified, ETag.
    """
    logger.info("Listing objects in s3://%s/%s", bucket, prefix)
    paginator = s3_client.get_paginator("list_objects_v2")
    page_kwargs = {"Bucket": bucket}
    if prefix:
        page_kwargs["Prefix"] = prefix

    try:
        total_count = 0
        for page in paginator.paginate(**page_kwargs):
            for obj in page.get("Contents", []):
                total_count += 1
                yield {
                    "Key": obj["Key"],
                    "Size": obj["Size"],
                    "LastModified": obj["LastModified"].isoformat(),
                    "ETag": obj["ETag"],
                }
        logger.info(
            "Listed %d objects in s3://%s/%s", total_count, bucket, prefix
        )
    except s3_client.exceptions.ClientError as e:
        raise _classify_s3_error(e, "list_objects_v2") from e


@exponential_backoff_with_jitter(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    retryable_exceptions=(RetryableError,),
)
def head_object(s3_client, bucket: str, key: str) -> Dict[str, Any]:
    """Get object metadata."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        return {
            "ContentLength": response["ContentLength"],
            "ETag": response.get("ETag", ""),
            "LastModified": response["LastModified"].isoformat(),
        }
    except s3_client.exceptions.ClientError as e:
        raise _classify_s3_error(e, "head_object") from e


@exponential_backoff_with_jitter(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    retryable_exceptions=(RetryableError,),
)
def copy_object(
    s3_client,
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    kms_key_id: str = "",
) -> Dict[str, Any]:
    """Server-side copy for objects < 5GB."""
    logger.info(
        "Copying s3://%s/%s -> s3://%s/%s",
        source_bucket,
        source_key,
        dest_bucket,
        dest_key,
    )
    copy_source = {"Bucket": source_bucket, "Key": source_key}
    kwargs = {
        "CopySource": copy_source,
        "Bucket": dest_bucket,
        "Key": dest_key,
    }

    if kms_key_id:
        kwargs["ServerSideEncryption"] = "aws:kms"
        kwargs["SSEKMSKeyId"] = kms_key_id

    try:
        response = s3_client.copy_object(**kwargs)
        logger.info("Copy complete: s3://%s/%s", dest_bucket, dest_key)
        return response
    except s3_client.exceptions.ClientError as e:
        raise _classify_s3_error(e, "copy_object") from e


@exponential_backoff_with_jitter(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    retryable_exceptions=(RetryableError,),
)
def multipart_copy(
    s3_client,
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    object_size: int,
    kms_key_id: str = "",
    part_size: int = DEFAULT_PART_SIZE,
) -> Dict[str, Any]:
    """Server-side multipart copy for objects >= 5GB."""
    if object_size > MAX_OBJECT_SIZE:
        raise ObjectTooLargeError(
            f"Object {source_key} size {object_size} exceeds max {MAX_OBJECT_SIZE}"
        )

    logger.info(
        "Multipart copy s3://%s/%s (%d bytes) -> s3://%s/%s",
        source_bucket,
        source_key,
        object_size,
        dest_bucket,
        dest_key,
    )

    create_kwargs = {
        "Bucket": dest_bucket,
        "Key": dest_key,
    }
    if kms_key_id:
        create_kwargs["ServerSideEncryption"] = "aws:kms"
        create_kwargs["SSEKMSKeyId"] = kms_key_id

    upload_id = None
    try:
        response = s3_client.create_multipart_upload(**create_kwargs)
        upload_id = response["UploadId"]

        num_parts = math.ceil(object_size / part_size)
        parts: List[Dict[str, Any]] = []
        copy_source = f"{source_bucket}/{source_key}"

        for part_num in range(1, num_parts + 1):
            start = (part_num - 1) * part_size
            end = min(part_num * part_size - 1, object_size - 1)
            byte_range = f"bytes={start}-{end}"

            part_response = s3_client.upload_part_copy(
                Bucket=dest_bucket,
                Key=dest_key,
                UploadId=upload_id,
                PartNumber=part_num,
                CopySource=copy_source,
                CopySourceRange=byte_range,
            )
            parts.append(
                {
                    "PartNumber": part_num,
                    "ETag": part_response["CopyPartResult"]["ETag"],
                }
            )
            logger.info(
                "Part %d/%d complete for %s", part_num, num_parts, dest_key
            )

        result = s3_client.complete_multipart_upload(
            Bucket=dest_bucket,
            Key=dest_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        logger.info("Multipart copy complete: s3://%s/%s", dest_bucket, dest_key)
        return result

    except Exception:
        if upload_id:
            logger.warning("Aborting multipart upload %s for %s", upload_id, dest_key)
            try:
                s3_client.abort_multipart_upload(
                    Bucket=dest_bucket, Key=dest_key, UploadId=upload_id
                )
            except Exception:
                logger.error(
                    "Failed to abort multipart upload %s", upload_id, exc_info=True
                )
        raise
