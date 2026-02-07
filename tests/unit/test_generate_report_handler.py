"""Tests for GenerateReport Lambda handler."""

import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from generate_report.handler import handler


class TestGenerateReportHandler:
    @mock_aws
    def test_handler_generates_report(self, mock_context):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")

        event = {
            "execution_id": "test-exec-001",
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test-exec-001/manifest.json",
            "total_objects": 50,
            "total_size_bytes": 1024000,
            "source_bucket": "source-bucket",
            "destination_bucket": "destination-bucket",
            "validation": {
                "status": "PASSED",
                "total_expected": 50,
                "total_found": 50,
                "samples_checked": 3,
                "samples_passed": 3,
                "failures": [],
            },
        }

        result = handler(event, mock_context)

        assert result["status"] == "PASSED"
        assert result["report_bucket"] == "manifest-bucket"
        assert "report_key" in result
        assert result["execution_id"] == "test-exec-001"

        # Verify report content
        report_obj = s3.get_object(
            Bucket="manifest-bucket", Key=result["report_key"]
        )
        report = json.loads(report_obj["Body"].read().decode())
        assert report["total_objects"] == 50
        assert report["status"] == "PASSED"

    @mock_aws
    def test_handler_sends_sns_notification(self, mock_context, monkeypatch):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")

        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="transfer-notifications")
        monkeypatch.setenv("SNS_TOPIC_ARN", topic["TopicArn"])

        event = {
            "execution_id": "test-exec-sns",
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test/manifest.json",
            "total_objects": 10,
            "total_size_bytes": 5000,
            "validation": {"status": "PASSED"},
        }

        result = handler(event, mock_context)
        assert result["notification_sent"] is True

    @mock_aws
    def test_handler_no_sns_when_topic_not_set(self, mock_context, monkeypatch):
        monkeypatch.setenv("SNS_TOPIC_ARN", "")

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")

        event = {
            "execution_id": "test-exec-no-sns",
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test/manifest.json",
            "total_objects": 10,
            "total_size_bytes": 5000,
            "validation": {"status": "PASSED"},
        }

        result = handler(event, mock_context)
        assert result["notification_sent"] is False

    @mock_aws
    def test_handler_reports_failed_status(self, mock_context):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")

        event = {
            "execution_id": "test-exec-fail",
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test/manifest.json",
            "total_objects": 100,
            "total_size_bytes": 500000,
            "validation": {
                "status": "FAILED",
                "total_expected": 100,
                "total_found": 95,
                "failures": [{"key": "file.txt", "reason": "missing"}],
            },
        }

        result = handler(event, mock_context)
        assert result["status"] == "FAILED"
