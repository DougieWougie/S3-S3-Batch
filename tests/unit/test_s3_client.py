"""Tests for S3 client wrapper."""

import pytest
from moto import mock_aws
import boto3

from common.s3_client import (
    copy_object,
    head_object,
    list_objects_paginated,
    multipart_copy,
)
from common.exceptions import ObjectTooLargeError


@pytest.fixture
def mocked_aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="src-bucket")
        s3.create_bucket(Bucket="dst-bucket")
        for i in range(3):
            s3.put_object(
                Bucket="src-bucket",
                Key=f"prefix/file{i}.txt",
                Body=f"content-{i}" * 50,
            )
        yield s3


class TestListObjectsPaginated:
    def test_lists_all_objects(self, mocked_aws):
        objects = list(list_objects_paginated(mocked_aws, "src-bucket", "prefix/"))
        assert len(objects) == 3
        keys = {o["Key"] for o in objects}
        assert keys == {"prefix/file0.txt", "prefix/file1.txt", "prefix/file2.txt"}
        for obj in objects:
            assert "Size" in obj
            assert "ETag" in obj

    def test_empty_prefix(self, mocked_aws):
        objects = list(list_objects_paginated(mocked_aws, "src-bucket"))
        assert len(objects) == 3

    def test_no_matching_objects(self, mocked_aws):
        objects = list(list_objects_paginated(mocked_aws, "src-bucket", "nonexistent/"))
        assert len(objects) == 0


class TestHeadObject:
    def test_head_object(self, mocked_aws):
        meta = head_object(mocked_aws, "src-bucket", "prefix/file0.txt")
        assert meta["ContentLength"] > 0
        assert "ETag" in meta
        assert "LastModified" in meta


class TestCopyObject:
    def test_copy_object(self, mocked_aws):
        copy_object(
            s3_client=mocked_aws,
            source_bucket="src-bucket",
            source_key="prefix/file0.txt",
            dest_bucket="dst-bucket",
            dest_key="copied/file0.txt",
        )
        # Verify the copy
        response = mocked_aws.get_object(Bucket="dst-bucket", Key="copied/file0.txt")
        body = response["Body"].read().decode()
        assert body == "content-0" * 50

    def test_copy_object_with_kms(self, mocked_aws):
        # KMS encryption param is passed but moto doesn't enforce it
        copy_object(
            s3_client=mocked_aws,
            source_bucket="src-bucket",
            source_key="prefix/file0.txt",
            dest_bucket="dst-bucket",
            dest_key="copied/file0.txt",
            kms_key_id="arn:aws:kms:us-east-1:111:key/test",
        )
        response = mocked_aws.get_object(Bucket="dst-bucket", Key="copied/file0.txt")
        assert response["Body"].read()


class TestMultipartCopy:
    def test_multipart_copy(self, mocked_aws):
        # Create a larger object (> part_size for testing with small part size)
        large_body = b"x" * (10 * 1024 * 1024)  # 10 MB
        mocked_aws.put_object(
            Bucket="src-bucket", Key="large/file.bin", Body=large_body
        )

        multipart_copy(
            s3_client=mocked_aws,
            source_bucket="src-bucket",
            source_key="large/file.bin",
            dest_bucket="dst-bucket",
            dest_key="copied/large.bin",
            object_size=len(large_body),
            part_size=5 * 1024 * 1024,  # 5MB parts
        )

        response = mocked_aws.get_object(Bucket="dst-bucket", Key="copied/large.bin")
        result = response["Body"].read()
        assert len(result) == len(large_body)

    def test_object_too_large_raises(self, mocked_aws):
        with pytest.raises(ObjectTooLargeError):
            multipart_copy(
                s3_client=mocked_aws,
                source_bucket="src-bucket",
                source_key="prefix/file0.txt",
                dest_bucket="dst-bucket",
                dest_key="copied/file0.txt",
                object_size=6 * 1024 * 1024 * 1024 * 1024,  # 6 TB
            )
