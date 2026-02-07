"""Shared fixtures for S3 transfer tests."""

import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

# Add lambda source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "lambda"))


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set AWS environment variables for testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    monkeypatch.setenv("SOURCE_ROLE_ARN", "arn:aws:iam::111111111111:role/SourceReaderRole")
    monkeypatch.setenv("DESTINATION_ROLE_ARN", "arn:aws:iam::222222222222:role/DestWriterRole")
    monkeypatch.setenv("EXTERNAL_ID", "test-external-id")
    monkeypatch.setenv("SOURCE_BUCKET", "source-bucket")
    monkeypatch.setenv("DESTINATION_BUCKET", "destination-bucket")
    monkeypatch.setenv("SOURCE_PREFIX", "data/")
    monkeypatch.setenv("DESTINATION_PREFIX", "transferred/")
    monkeypatch.setenv("MANIFEST_BUCKET", "manifest-bucket")
    monkeypatch.setenv("SOURCE_KMS_KEY_ID", "arn:aws:kms:us-east-1:111111111111:key/source-key")
    monkeypatch.setenv("DESTINATION_KMS_KEY_ID", "arn:aws:kms:us-east-1:222222222222:key/dest-key")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:transfer-notifications")
    monkeypatch.setenv("VALIDATION_SAMPLE_SIZE", "3")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest.fixture
def mock_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.aws_request_id = "test-request-id-12345"
    ctx.function_name = "test-function"
    ctx.memory_limit_in_mb = 256
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:test"
    return ctx


@pytest.fixture
def s3_client():
    """Create a moto-mocked S3 client."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        yield client


@pytest.fixture
def setup_source_bucket(s3_client):
    """Create source bucket with sample objects."""
    s3_client.create_bucket(Bucket="source-bucket")
    for i in range(5):
        s3_client.put_object(
            Bucket="source-bucket",
            Key=f"data/file{i}.txt",
            Body=f"content of file {i}" * 100,
        )
    return s3_client


@pytest.fixture
def setup_manifest_bucket(s3_client):
    """Create manifest bucket."""
    s3_client.create_bucket(Bucket="manifest-bucket")
    return s3_client


@pytest.fixture
def setup_destination_bucket(s3_client):
    """Create destination bucket."""
    s3_client.create_bucket(Bucket="destination-bucket")
    return s3_client
