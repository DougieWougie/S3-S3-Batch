"""Tests for configuration loading."""

import pytest

from common.config import TransferConfig


class TestTransferConfig:
    def test_from_env_loads_all_values(self):
        config = TransferConfig.from_env()
        assert config.source_role_arn == "arn:aws:iam::111111111111:role/SourceReaderRole"
        assert config.destination_role_arn == "arn:aws:iam::222222222222:role/DestWriterRole"
        assert config.external_id == "test-external-id"
        assert config.source_bucket == "source-bucket"
        assert config.destination_bucket == "destination-bucket"
        assert config.source_prefix == "data/"
        assert config.destination_prefix == "transferred/"
        assert config.manifest_bucket == "manifest-bucket"
        assert config.validation_sample_size == 3

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("SOURCE_ROLE_ARN", raising=False)
        monkeypatch.delenv("DESTINATION_ROLE_ARN", raising=False)
        monkeypatch.delenv("EXTERNAL_ID", raising=False)
        monkeypatch.delenv("SOURCE_BUCKET", raising=False)
        monkeypatch.delenv("DESTINATION_BUCKET", raising=False)
        monkeypatch.delenv("SOURCE_PREFIX", raising=False)
        monkeypatch.delenv("DESTINATION_PREFIX", raising=False)
        monkeypatch.delenv("MANIFEST_BUCKET", raising=False)
        monkeypatch.delenv("VALIDATION_SAMPLE_SIZE", raising=False)
        monkeypatch.delenv("SNS_TOPIC_ARN", raising=False)

        config = TransferConfig.from_env()
        assert config.source_role_arn == ""
        assert config.external_id == ""
        assert config.multipart_threshold_bytes == 5 * 1024 * 1024 * 1024
        assert config.multipart_chunk_size_bytes == 100 * 1024 * 1024
        assert config.max_retry_attempts == 5
        assert config.retry_base_delay == 1.0
        assert config.retry_max_delay == 60.0
        assert config.validation_sample_size == 10

    def test_frozen_dataclass(self):
        config = TransferConfig.from_env()
        with pytest.raises(AttributeError):
            config.source_bucket = "modified"
