import configparser
import json
from io import BytesIO
from pathlib import PosixPath

import boto3
import pytest
from moto import mock_s3, mock_sqs, mock_ssm, mock_sts
from pytest_mock import MockerFixture

from cli.constants import AWS_DEFAULT_REGION
from cli.parameter_store.utils import (
    filename_from_obj,
    get_bucket_name,
    get_queue_name,
    get_queue_url,
)


@pytest.fixture(autouse=True, scope="session")
def mock_queue_url(session_mocker):
    def mock_get_queue_url(env):
        account_id = "123456789012"
        return f"https://sqs.us-east-2.amazonaws.com/{account_id}/{get_queue_name(env)}"

    session_mocker.patch("cli.parameter_store.utils.get_queue_url", mock_get_queue_url)


@pytest.fixture
def mock_s3_client():
    with mock_s3():
        yield boto3.client("s3", region_name=AWS_DEFAULT_REGION)


@pytest.fixture()
def mock_sts_client():
    with mock_sts():
        yield boto3.client("sts", region_name=AWS_DEFAULT_REGION)


@pytest.fixture
def mock_sqs_client():
    with mock_sqs():
        yield boto3.client("sqs", region_name=AWS_DEFAULT_REGION)


@pytest.fixture
def mock_ssm_client():
    with mock_ssm():
        yield boto3.client("ssm", region_name=AWS_DEFAULT_REGION)


@pytest.fixture(autouse=True)
def mock_aws_config(mocker: MockerFixture):
    dummy_config_data = {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Developer",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Developer",
        },
    }
    dummy_config = configparser.RawConfigParser(default_section="default")
    dummy_config.clear()
    dummy_config.read_dict(dummy_config_data)
    return mocker.patch(
        "cli.services.aws.config_service.load_config_from_file",
        return_value=dummy_config,
    )


@pytest.fixture(autouse=True, scope="session")
def mock_aws_sso_cache(session_mocker: MockerFixture):
    dummy_cache = PosixPath(__file__).parent / "services/aws/mock_sso_cache"
    session_mocker.patch(
        "cli.services.aws.config_service.AWSConfigService._sso_cache",
        return_value=dummy_cache.glob("*.json"),
    )


@pytest.fixture
def mock_s3_notification_message(mocker, mock_sqs_client):
    def _mock_s3_notification_message(env, key):
        queue_name = get_queue_name(env)
        request = {
            "Records": [
                {
                    "eventVersion": "2.2",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-west-2",
                    "eventTime": "The time, in ISO-8601 format, for example, 1970-01-01T00:00:00.000Z, when Amazon"
                    + " S3 finished processing the request",
                    "eventName": "event-type",
                    "userIdentity": {
                        "principalId": "Amazon-customer-ID-of-the-user-who-caused-the-event"
                    },
                    "requestParameters": {
                        "sourceIPAddress": "ip-address-where-request-came-from"
                    },
                    "responseElements": {
                        "x-amz-request-id": "Amazon S3 generated request ID",
                        "x-amz-id-2": "Amazon S3 host that processed the request",
                    },
                    "s3": {
                        "s3SchemaVersion": "1.0",
                        "configurationId": "ID found in the bucket notification configuration",
                        "bucket": {
                            "name": get_bucket_name(env),
                            "ownerIdentity": {
                                "principalId": "Amazon-customer-ID-of-the-bucket-owner"
                            },
                            "arn": "bucket-ARN",
                        },
                        "object": {
                            "key": f"{key}",
                            "size": "object-size in bytes",
                            "eTag": "object eTag",
                            "versionId": "object version if bucket is versioning-enabled, otherwise null",
                            "sequencer": "a string representation of a hexadecimal value used to determine event "
                            + "sequence, only used with PUTs and DELETEs",
                        },
                    },
                    "glacierEventData": {
                        "restoreEventData": {
                            "lifecycleRestorationExpiryTime": "The time, in ISO-8601 format, for example, "
                            + "1970-01-01T00:00:00.000Z, of Restore Expiry",
                            "lifecycleRestoreStorageClass": "Source storage class for restore",
                        }
                    },
                }
            ]
        }
        resp = mock_sqs_client.create_queue(
            QueueName=queue_name,
        )
        queue_url = resp["QueueUrl"]
        resp = mock_sqs_client.send_message(
            QueueUrl=queue_url, MessageBody=json.dumps(request)
        )
        return resp

    return _mock_s3_notification_message


@pytest.fixture
def mock_make_bucket(mock_s3_client):
    def _make_bucket(env):
        region = "us-east-2"
        mock_s3_client.create_bucket(
            Bucket=get_bucket_name(env="qa"),
            CreateBucketConfiguration={"LocationConstraint": region},
        )
        return mock_s3_client

    return _make_bucket


@pytest.fixture
def mock_put_request(mock_make_bucket, mock_s3_notification_message):
    def _put_request(env):
        s3_client = mock_make_bucket(env)
        request = {
            "path": "/qa/abc",
            "encrypt": False,
            "value": "def",
            "notes": [
                {
                    "author": "someone@testing.com",
                    "subject": "please",
                    "body": "help me ok",
                    "added": "20220801-170539",
                }
            ],
            "requester": "someone@testing.com",
            "id": "4066b026-31e4-4e06-905b-b40f5c602014",
            "requested_at": "20220801-170539",
            "touches": 0,
            "reviewed_at": "",
        }
        filename = filename_from_obj(request)
        obj = BytesIO(initial_bytes=json.dumps(request).encode("utf-8"))
        s3_client.upload_fileobj(
            Fileobj=obj, Bucket=get_bucket_name(env=env), Key=filename
        )
        message = mock_s3_notification_message(env=env, key=filename)
        return filename, get_bucket_name(env=env), request, message

    return _put_request


@pytest.fixture
def mock_upload_s3_obj(mock_s3_client):
    def _mock_upload_s3_obj(obj, key, env, bucket=None):
        bucket = bucket or get_bucket_name(env=env)
        return mock_s3_client.upload_fileobj(obj, Bucket=bucket, Key=key)

    return _mock_upload_s3_obj


@pytest.fixture
def mock_get_s3_obj(mock_s3_client):
    def _mock_upload_s3_obj(key, env, bucket=None):
        bucket = bucket or get_bucket_name(env=env)
        return mock_s3_client.get_object(Bucket=bucket, Key=key)

    return _mock_upload_s3_obj


@pytest.fixture
def mock_delete_s3_obj(mock_s3_client):
    def _mock_delete_s3_obj(key, env, bucket=None):
        bucket = bucket or get_bucket_name(env=env)
        return mock_s3_client.delete_object(Bucket=bucket, Key=key)

    return _mock_delete_s3_obj


@pytest.fixture
def mock_receive_sqs_message(mock_sqs_client):
    def _mock_receive_sqs_message(env, queue_url=None):
        queue_url = queue_url or get_queue_url(env)
        return mock_sqs_client.receive_message(QueueUrl=queue_url)

    return _mock_receive_sqs_message


@pytest.fixture
def mock_all_aws(
    mocker,
    mock_aws_config,
    mock_upload_s3_obj,
    mock_get_s3_obj,
    mock_delete_s3_obj,
    mock_receive_sqs_message,
):
    mocker.patch(
        "cli.services.aws.clients_service.get_user_for_env",
        return_value="TEST@testing.com",
    )
    mocker.patch("cli.parameter_store.validate.get_parameter")
    mocker.patch(
        "cli.parameter_store.requests_client.upload_s3_obj", mock_upload_s3_obj
    )
    mocker.patch("cli.parameter_store.requests_client.get_s3_obj", mock_get_s3_obj)
    mocker.patch(
        "cli.parameter_store.requests_client.delete_s3_obj", mock_delete_s3_obj
    )
    mocker.patch(
        "cli.parameter_store.requests_client.receive_sqs_message",
        mock_receive_sqs_message,
    )
    mocker.patch(
        "cli.parameter_store.requests_client.restore_sqs_message",
    )
    mocker.patch(
        "cli.parameter_store.requests_client.delete_sqs_message",
    )
