"""ListObjects Lambda: assumes source role, paginated list, writes manifest to S3."""

import json
import logging
import uuid
from datetime import datetime, timezone

import boto3

from common.config import TransferConfig
from common.exceptions import ManifestError, NonRetryableError
from common.logger import get_logger, log_with_context
from common.sts_client import assume_role, get_boto3_client

logger = get_logger(__name__)


def handler(event: dict, context) -> dict:
    """List objects in source bucket and write manifest to manifest bucket.

    Input event:
        {
            "source_prefix": "optional/override/prefix/"
        }

    Returns:
        {
            "manifest_bucket": "...",
            "manifest_key": "...",
            "total_objects": 123,
            "total_size_bytes": 456789,
            "execution_id": "...",
        }
    """
    request_id = getattr(context, "aws_request_id", "local")
    log_with_context(logger, logging.INFO, "ListObjects started", request_id=request_id)

    config = TransferConfig.from_env()
    source_prefix = event.get("source_prefix", config.source_prefix)
    execution_id = event.get("execution_id", str(uuid.uuid4()))

    # Assume source role to list objects
    credentials = assume_role(
        role_arn=config.source_role_arn,
        session_name=f"ListObjects-{execution_id[:8]}",
        external_id=config.external_id,
    )
    source_s3 = get_boto3_client("s3", credentials)

    # Paginated listing
    objects = []
    total_size = 0
    paginator = source_s3.get_paginator("list_objects_v2")
    page_kwargs = {"Bucket": config.source_bucket}
    if source_prefix:
        page_kwargs["Prefix"] = source_prefix

    try:
        for page in paginator.paginate(**page_kwargs):
            for obj in page.get("Contents", []):
                item = {
                    "Key": obj["Key"],
                    "Size": obj["Size"],
                    "ETag": obj["ETag"],
                }
                objects.append(item)
                total_size += obj["Size"]
    except source_s3.exceptions.ClientError as e:
        raise NonRetryableError(
            f"Failed to list objects in s3://{config.source_bucket}/{source_prefix}: {e}"
        ) from e

    log_with_context(
        logger,
        logging.INFO,
        "Object listing complete",
        request_id=request_id,
        total_objects=len(objects),
        total_size_bytes=total_size,
    )

    if not objects:
        log_with_context(
            logger, logging.WARNING, "No objects found to transfer", request_id=request_id
        )

    # Write manifest to manifest bucket
    manifest = {
        "execution_id": execution_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_bucket": config.source_bucket,
        "source_prefix": source_prefix,
        "destination_bucket": config.destination_bucket,
        "destination_prefix": config.destination_prefix,
        "total_objects": len(objects),
        "total_size_bytes": total_size,
        "objects": objects,
    }

    manifest_key = f"manifests/{execution_id}/manifest.json"
    hub_s3 = boto3.client("s3")

    try:
        hub_s3.put_object(
            Bucket=config.manifest_bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, default=str),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
    except hub_s3.exceptions.ClientError as e:
        raise ManifestError(
            f"Failed to write manifest to s3://{config.manifest_bucket}/{manifest_key}: {e}"
        ) from e

    log_with_context(
        logger,
        logging.INFO,
        "Manifest written",
        request_id=request_id,
        manifest_key=manifest_key,
    )

    return {
        "manifest_bucket": config.manifest_bucket,
        "manifest_key": manifest_key,
        "total_objects": len(objects),
        "total_size_bytes": total_size,
        "execution_id": execution_id,
        "source_bucket": config.source_bucket,
        "source_prefix": source_prefix,
        "destination_bucket": config.destination_bucket,
        "destination_prefix": config.destination_prefix,
    }
