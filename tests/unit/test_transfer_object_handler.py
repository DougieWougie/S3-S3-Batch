"""Tests for TransferObject Lambda handler."""

from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from transfer_object.handler import handler


class TestTransferObjectHandler:
    @mock_aws
    @patch("transfer_object.handler.assume_role")
    @patch("transfer_object.handler.get_boto3_client")
    def test_handler_copies_small_object(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="source-bucket")
        s3.create_bucket(Bucket="destination-bucket")
        s3.put_object(
            Bucket="source-bucket", Key="data/test.txt", Body="hello world"
        )

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        event = {
            "Key": "data/test.txt",
            "Size": 11,
            "ETag": '"abc123"',
            "source_bucket": "source-bucket",
            "destination_bucket": "destination-bucket",
            "destination_prefix": "transferred/",
            "source_prefix": "data/",
            "execution_id": "test-exec",
        }
        result = handler(event, mock_context)

        assert result["status"] == "SUCCESS"
        assert result["source_key"] == "data/test.txt"
        assert result["dest_key"] == "transferred/test.txt"

        # Verify file was copied
        obj = s3.get_object(Bucket="destination-bucket", Key="transferred/test.txt")
        assert obj["Body"].read().decode() == "hello world"

    @mock_aws
    @patch("transfer_object.handler.assume_role")
    @patch("transfer_object.handler.get_boto3_client")
    def test_handler_preserves_key_without_prefix(
        self, mock_get_client, mock_assume_role, mock_context, monkeypatch
    ):
        monkeypatch.setenv("SOURCE_PREFIX", "")
        monkeypatch.setenv("DESTINATION_PREFIX", "")

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="source-bucket")
        s3.create_bucket(Bucket="destination-bucket")
        s3.put_object(Bucket="source-bucket", Key="simple.txt", Body="data")

        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = s3

        event = {
            "Key": "simple.txt",
            "Size": 4,
            "ETag": '"abc"',
            "source_prefix": "",
            "destination_prefix": "",
            "execution_id": "test-exec",
        }
        result = handler(event, mock_context)

        assert result["dest_key"] == "simple.txt"
        obj = s3.get_object(Bucket="destination-bucket", Key="simple.txt")
        assert obj["Body"].read().decode() == "data"

    @mock_aws
    @patch("transfer_object.handler.assume_role")
    @patch("transfer_object.handler.get_boto3_client")
    def test_handler_raises_on_copy_failure(
        self, mock_get_client, mock_assume_role, mock_context
    ):
        mock_s3 = MagicMock()
        mock_assume_role.return_value = {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "test",
        }
        mock_get_client.return_value = mock_s3

        from botocore.exceptions import ClientError
        mock_s3.copy_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "CopyObject",
        )
        mock_s3.exceptions.ClientError = ClientError

        event = {
            "Key": "data/test.txt",
            "Size": 11,
            "ETag": '"abc"',
            "execution_id": "fail-test",
        }
        with pytest.raises(Exception):
            handler(event, mock_context)
