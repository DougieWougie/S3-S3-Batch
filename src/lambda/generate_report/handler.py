"""GenerateReport Lambda: JSON report to S3, optional SNS notification."""

import json
import logging
from datetime import datetime, timezone

import boto3

from common.config import TransferConfig
from common.exceptions import NonRetryableError
from common.logger import get_logger, log_with_context

logger = get_logger(__name__)


def handler(event: dict, context) -> dict:
    """Generate a summary report and optionally notify via SNS.

    Input event:
        {
            "execution_id": "...",
            "manifest_bucket": "...",
            "manifest_key": "...",
            "total_objects": 123,
            "total_size_bytes": 456789,
            "validation": {
                "status": "PASSED",
                "total_expected": 123,
                "total_found": 123,
                ...
            },
            "source_bucket": "...",
            "destination_bucket": "...",
        }

    Returns:
        {
            "report_bucket": "...",
            "report_key": "...",
            "status": "COMPLETED",
            "notification_sent": true|false,
        }
    """
    request_id = getattr(context, "aws_request_id", "local")
    config = TransferConfig.from_env()
    execution_id = event.get("execution_id", "unknown")

    log_with_context(
        logger,
        logging.INFO,
        "GenerateReport started",
        request_id=request_id,
        execution_id=execution_id,
    )

    validation = event.get("validation", {})
    transfer_status = validation.get("status", "UNKNOWN")

    report = {
        "execution_id": execution_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": transfer_status,
        "source_bucket": event.get("source_bucket", config.source_bucket),
        "source_prefix": event.get("source_prefix", config.source_prefix),
        "destination_bucket": event.get("destination_bucket", config.destination_bucket),
        "destination_prefix": event.get("destination_prefix", config.destination_prefix),
        "total_objects": event.get("total_objects", 0),
        "total_size_bytes": event.get("total_size_bytes", 0),
        "validation": validation,
        "manifest_location": f"s3://{event.get('manifest_bucket', '')}/{event.get('manifest_key', '')}",
    }

    # Write report to manifest bucket
    report_key = f"reports/{execution_id}/report.json"
    hub_s3 = boto3.client("s3")

    try:
        hub_s3.put_object(
            Bucket=config.manifest_bucket,
            Key=report_key,
            Body=json.dumps(report, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
    except Exception as e:
        raise NonRetryableError(
            f"Failed to write report to s3://{config.manifest_bucket}/{report_key}: {e}"
        ) from e

    log_with_context(
        logger,
        logging.INFO,
        "Report written",
        request_id=request_id,
        report_key=report_key,
    )

    # Optional SNS notification
    notification_sent = False
    if config.sns_topic_arn:
        try:
            sns_client = boto3.client("sns")
            subject = f"S3 Transfer {transfer_status}: {execution_id[:8]}"
            message = json.dumps(
                {
                    "execution_id": execution_id,
                    "status": transfer_status,
                    "total_objects": report["total_objects"],
                    "total_size_bytes": report["total_size_bytes"],
                    "source": f"s3://{report['source_bucket']}/{report['source_prefix']}",
                    "destination": f"s3://{report['destination_bucket']}/{report['destination_prefix']}",
                    "report_location": f"s3://{config.manifest_bucket}/{report_key}",
                },
                indent=2,
            )
            sns_client.publish(
                TopicArn=config.sns_topic_arn,
                Subject=subject[:100],
                Message=message,
            )
            notification_sent = True
            log_with_context(
                logger,
                logging.INFO,
                "SNS notification sent",
                request_id=request_id,
                topic_arn=config.sns_topic_arn,
            )
        except Exception as e:
            log_with_context(
                logger,
                logging.WARNING,
                f"Failed to send SNS notification: {e}",
                request_id=request_id,
            )

    return {
        "report_bucket": config.manifest_bucket,
        "report_key": report_key,
        "status": transfer_status,
        "notification_sent": notification_sent,
        "execution_id": execution_id,
    }
