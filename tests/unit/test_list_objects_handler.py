"""Tests for ListObjects Lambda handler."""

from unittest.mock import patch, MagicMock
import json

import boto3
import pytest
from moto import mock_aws

from list_objects.handler import handler


class TestListObjectsHandler:
    @mock_aws
    @patch("list_objects.handler.assume_role")
    @patch("list_objects.handler.get_boto3_client")
    def test_handler_lists_and_writes_manifest(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        # Setup mocked S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="source-bucket")
        s3.create_bucket(Bucket="manifest-bucket")
        for i in range(3):
            s3.put_object(
                Bucket="source-bucket",
                Key=f"data/file{i}.txt",
                Body=f"content-{i}",
            )

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        # Return moto s3 client as the "cross-account" client
        mock_get_client.return_value = s3

        event = {"execution_id": "test-exec-001"}
        result = handler(event, mock_context)

        assert result["total_objects"] == 3
        assert result["execution_id"] == "test-exec-001"
        assert result["manifest_bucket"] == "manifest-bucket"
        assert "manifest_key" in result

        # Verify manifest was written
        manifest_obj = s3.get_object(
            Bucket="manifest-bucket", Key=result["manifest_key"]
        )
        manifest = json.loads(manifest_obj["Body"].read().decode())
        assert manifest["total_objects"] == 3
        assert len(manifest["objects"]) == 3

    @mock_aws
    @patch("list_objects.handler.assume_role")
    @patch("list_objects.handler.get_boto3_client")
    def test_handler_empty_bucket(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="source-bucket")
        s3.create_bucket(Bucket="manifest-bucket")

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        result = handler({"execution_id": "empty-test"}, mock_context)
        assert result["total_objects"] == 0
        assert result["total_size_bytes"] == 0

    @mock_aws
    @patch("list_objects.handler.assume_role")
    @patch("list_objects.handler.get_boto3_client")
    def test_handler_uses_event_prefix(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="source-bucket")
        s3.create_bucket(Bucket="manifest-bucket")
        s3.put_object(Bucket="source-bucket", Key="custom/a.txt", Body="a")
        s3.put_object(Bucket="source-bucket", Key="data/b.txt", Body="b")

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        result = handler(
            {"source_prefix": "custom/", "execution_id": "prefix-test"},
            mock_context,
        )
        assert result["total_objects"] == 1
