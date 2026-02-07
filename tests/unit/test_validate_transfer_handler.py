"""Tests for ValidateTransfer Lambda handler."""

import json
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from common.exceptions import ValidationError
from validate_transfer.handler import handler


class TestValidateTransferHandler:
    @mock_aws
    @patch("validate_transfer.handler.assume_role")
    @patch("validate_transfer.handler.get_boto3_client")
    def test_handler_validation_passes(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")
        s3.create_bucket(Bucket="destination-bucket")

        # Create destination objects
        for i in range(3):
            body = f"content-{i}"
            s3.put_object(
                Bucket="destination-bucket",
                Key=f"transferred/file{i}.txt",
                Body=body,
            )

        # Create manifest
        manifest = {
            "execution_id": "test-exec",
            "source_bucket": "source-bucket",
            "source_prefix": "data/",
            "destination_bucket": "destination-bucket",
            "destination_prefix": "transferred/",
            "total_objects": 3,
            "objects": [
                {"Key": f"data/file{i}.txt", "Size": len(f"content-{i}"), "ETag": f'"e{i}"'}
                for i in range(3)
            ],
        }
        s3.put_object(
            Bucket="manifest-bucket",
            Key="manifests/test-exec/manifest.json",
            Body=json.dumps(manifest),
        )

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        event = {
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test-exec/manifest.json",
            "total_objects": 3,
            "execution_id": "test-exec",
            "destination_bucket": "destination-bucket",
            "destination_prefix": "transferred/",
        }
        result = handler(event, mock_context)
        assert result["status"] == "PASSED"
        assert result["total_expected"] == 3
        assert result["total_found"] == 3

    @mock_aws
    @patch("validate_transfer.handler.assume_role")
    @patch("validate_transfer.handler.get_boto3_client")
    def test_handler_validation_fails_missing_objects(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="manifest-bucket")
        s3.create_bucket(Bucket="destination-bucket")

        # Only create 1 of 3 expected objects
        s3.put_object(
            Bucket="destination-bucket",
            Key="transferred/file0.txt",
            Body="content-0",
        )

        manifest = {
            "execution_id": "test-exec",
            "source_bucket": "source-bucket",
            "source_prefix": "data/",
            "destination_bucket": "destination-bucket",
            "destination_prefix": "transferred/",
            "total_objects": 3,
            "objects": [
                {"Key": f"data/file{i}.txt", "Size": len(f"content-{i}"), "ETag": f'"e{i}"'}
                for i in range(3)
            ],
        }
        s3.put_object(
            Bucket="manifest-bucket",
            Key="manifests/test-exec/manifest.json",
            Body=json.dumps(manifest),
        )

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        event = {
            "manifest_bucket": "manifest-bucket",
            "manifest_key": "manifests/test-exec/manifest.json",
            "total_objects": 3,
            "execution_id": "test-exec",
            "destination_bucket": "destination-bucket",
            "destination_prefix": "transferred/",
        }
        with pytest.raises(ValidationError):
            handler(event, mock_context)
