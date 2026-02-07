"""Tests for STS client with credential caching."""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

from common.exceptions import AccessDeniedError, RetryableError
from common.sts_client import (
    assume_role,
    clear_credential_cache,
    get_boto3_client,
    _credential_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear credential cache before each test."""
    clear_credential_cache()
    yield
    clear_credential_cache()


class TestAssumeRole:
    @patch("common.sts_client.boto3.client")
    def test_assume_role_success(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_boto_client.return_value = mock_sts
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_TEST",
                "SecretAccessKey": "secret_test",
                "SessionToken": "token_test",
                "Expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        }

        creds = assume_role(
            role_arn="arn:aws:iam::111111111111:role/TestRole",
            session_name="test-session",
        )

        assert creds["aws_access_key_id"] == "AKIA_TEST"
        assert creds["aws_secret_access_key"] == "secret_test"
        assert creds["aws_session_token"] == "token_test"

    @patch("common.sts_client.boto3.client")
    def test_assume_role_with_external_id(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_boto_client.return_value = mock_sts
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_TEST",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        }

        assume_role(
            role_arn="arn:aws:iam::111111111111:role/TestRole",
            external_id="ext-123",
        )

        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["ExternalId"] == "ext-123"

    @patch("common.sts_client.boto3.client")
    def test_credential_caching(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_boto_client.return_value = mock_sts
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_CACHED",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        }

        role_arn = "arn:aws:iam::111111111111:role/CachedRole"
        creds1 = assume_role(role_arn=role_arn)
        creds2 = assume_role(role_arn=role_arn)

        # STS should only be called once
        assert mock_sts.assume_role.call_count == 1
        assert creds1 == creds2

    @patch("common.sts_client.boto3.client")
    def test_access_denied_raises_non_retryable(self, mock_boto_client):
        from botocore.exceptions import ClientError

        mock_sts = MagicMock()
        mock_boto_client.return_value = mock_sts
        mock_sts.exceptions.ClientError = ClientError
        mock_sts.assume_role.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Not allowed"}},
            "AssumeRole",
        )

        with pytest.raises(AccessDeniedError):
            assume_role(role_arn="arn:aws:iam::111111111111:role/Denied")


class TestGetBoto3Client:
    @patch("common.sts_client.boto3.client")
    def test_creates_client_with_credentials(self, mock_boto_client):
        creds = {
            "aws_access_key_id": "AKIA_TEST",
            "aws_secret_access_key": "secret",
            "aws_session_token": "token",
        }
        get_boto3_client("s3", creds)

        mock_boto_client.assert_called_with(
            service_name="s3",
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="secret",
            aws_session_token="token",
        )

    @patch("common.sts_client.boto3.client")
    def test_creates_client_with_region(self, mock_boto_client):
        creds = {
            "aws_access_key_id": "AKIA_TEST",
            "aws_secret_access_key": "secret",
            "aws_session_token": "token",
        }
        get_boto3_client("s3", creds, region="eu-west-1")

        mock_boto_client.assert_called_with(
            service_name="s3",
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="secret",
            aws_session_token="token",
            region_name="eu-west-1",
        )
