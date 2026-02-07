"""ValidateTransfer Lambda: count verification + random sample ContentLength checks."""

import json
import logging
import random

import boto3

from common.config import TransferConfig
from common.exceptions import NonRetryableError, ValidationError
from common.logger import get_logger, log_with_context
from common.s3_client import head_object
from common.sts_client import assume_role, get_boto3_client

logger = get_logger(__name__)


def handler(event: dict, context) -> dict:
    """Validate that transfer completed correctly.

    Input event:
        {
            "manifest_bucket": "...",
            "manifest_key": "...",
            "total_objects": 123,
            "execution_id": "...",
            "source_bucket": "...",
            "destination_bucket": "...",
            "destination_prefix": "...",
        }

    Returns:
        {
            "status": "PASSED" | "FAILED",
            "total_expected": 123,
            "total_found": 123,
            "samples_checked": 10,
            "samples_passed": 10,
            "failures": [...],
        }
    """
    request_id = getattr(context, "aws_request_id", "local")
    config = TransferConfig.from_env()
    execution_id = event.get("execution_id", "unknown")

    log_with_context(
        logger,
        logging.INFO,
        "ValidateTransfer started",
        request_id=request_id,
        execution_id=execution_id,
    )

    # Read manifest from S3
    manifest_bucket = event["manifest_bucket"]
    manifest_key = event["manifest_key"]
    hub_s3 = boto3.client("s3")

    try:
        response = hub_s3.get_object(Bucket=manifest_bucket, Key=manifest_key)
        manifest = json.loads(response["Body"].read().decode("utf-8"))
    except Exception as e:
        raise NonRetryableError(
            f"Failed to read manifest from s3://{manifest_bucket}/{manifest_key}: {e}"
        ) from e

    objects = manifest["objects"]
    total_expected = len(objects)
    source_prefix = manifest.get("source_prefix", config.source_prefix)
    dest_prefix = event.get("destination_prefix", config.destination_prefix)
    dest_bucket = event.get("destination_bucket", config.destination_bucket)

    # Count verification: list destination objects
    dest_credentials = assume_role(
        role_arn=config.destination_role_arn,
        session_name=f"Validate-{execution_id[:8]}",
        external_id=config.external_id,
    )
    dest_s3 = get_boto3_client("s3", dest_credentials)

    dest_count = 0
    paginator = dest_s3.get_paginator("list_objects_v2")
    page_kwargs = {"Bucket": dest_bucket}
    if dest_prefix:
        page_kwargs["Prefix"] = dest_prefix

    try:
        for page in paginator.paginate(**page_kwargs):
            dest_count += page.get("KeyCount", 0)
    except Exception as e:
        raise NonRetryableError(
            f"Failed to list destination objects: {e}"
        ) from e

    log_with_context(
        logger,
        logging.INFO,
        "Count verification",
        request_id=request_id,
        expected=total_expected,
        found=dest_count,
    )

    # Sample ContentLength checks
    sample_size = min(config.validation_sample_size, total_expected)
    samples = random.sample(objects, sample_size) if objects else []

    failures = []
    samples_passed = 0

    for obj in samples:
        source_key = obj["Key"]
        expected_size = obj["Size"]

        if source_prefix and source_key.startswith(source_prefix):
            relative_key = source_key[len(source_prefix):]
        else:
            relative_key = source_key

        dest_key = f"{dest_prefix}{relative_key}" if dest_prefix else relative_key

        try:
            dest_meta = head_object(dest_s3, dest_bucket, dest_key)
            if dest_meta["ContentLength"] == expected_size:
                samples_passed += 1
            else:
                failures.append(
                    {
                        "key": dest_key,
                        "expected_size": expected_size,
                        "actual_size": dest_meta["ContentLength"],
                        "reason": "size_mismatch",
                    }
                )
        except Exception as e:
            failures.append(
                {
                    "key": dest_key,
                    "expected_size": expected_size,
                    "reason": f"head_object_failed: {e}",
                }
            )

    status = "PASSED" if (dest_count >= total_expected and not failures) else "FAILED"

    result = {
        "status": status,
        "total_expected": total_expected,
        "total_found": dest_count,
        "samples_checked": sample_size,
        "samples_passed": samples_passed,
        "failures": failures,
        "execution_id": execution_id,
        "manifest_bucket": manifest_bucket,
        "manifest_key": manifest_key,
        "destination_bucket": dest_bucket,
    }

    log_with_context(
        logger,
        logging.INFO,
        f"Validation {status}",
        request_id=request_id,
        **result,
    )

    if status == "FAILED":
        raise ValidationError(
            f"Transfer validation failed: expected {total_expected}, found {dest_count}, "
            f"{len(failures)} sample failures",
            details=result,
        )

    return result
