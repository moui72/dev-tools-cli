import configparser
import json
from contextlib import nullcontext as does_not_raise

import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture

from cli.constants import ALL_CORE_ENVS, AWS_ACCOUNT_TO_ENV
from cli.parameter_store.exceptions import RetryReviewNotAllowed
from cli.parameter_store.requests_client import RequestsClient, next_sqs_message
from cli.parameter_store.types import RequestType
from cli.services.aws.config_service import AWS_CFG

CORE_ENVS = [env.lower() for env in ALL_CORE_ENVS]

expected_profile_by_env = [
    (
        env,
        "profile dev-qa"
        if env.lower() in AWS_ACCOUNT_TO_ENV["12345678902"]
        else "profile dev",
    )
    for env in CORE_ENVS
]


@pytest.mark.parametrize("env,expected_profile", expected_profile_by_env)
def test_aws_config_get_profile_for_env(env, expected_profile):
    assert AWS_CFG.get_profile_name_for_env(env) == expected_profile


def test_request_client__next_sqs_message__success(
    mocker,
    mock_put_request,
    mock_all_aws,
):
    dummy_config_data = {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
        },
    }
    dummy_config = configparser.RawConfigParser(default_section="default")
    dummy_config.read_dict(dummy_config_data)
    AWS_CFG._reset()
    mocker.patch.object(AWS_CFG, "_config", dummy_config)

    mock_put_request("qa")

    with next_sqs_message("qa") as message:
        req, _ = RequestsClient.fetch_s3_object_from_sqs_message(
            env="qa", message=message
        )
        assert req == {
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


def test_request_client__delete_request__success(
    mocker, mock_put_request, mock_s3_client, mock_delete_s3_obj
):
    key, bucket, _, _ = mock_put_request("qa")
    mocker.patch(
        "cli.parameter_store.requests_client.delete_s3_obj", mock_delete_s3_obj
    )
    RequestsClient.delete_request("qa", key)
    with pytest.raises(ClientError) as ce:
        mock_s3_client.get_object(Key=key, Bucket=bucket)
        assert ce.error_response["Code"] == "NoSuchKey"


@pytest.mark.parametrize(
    "retry, prefix, expected_result",
    [
        (True, "rejected", pytest.raises(RetryReviewNotAllowed)),
        (True, "accepted", pytest.raises(RetryReviewNotAllowed)),
        (True, "requested", does_not_raise()),
        (False, "accepted", does_not_raise()),
        (False, "rejected", does_not_raise()),
        (False, "requested", does_not_raise()),
    ],
)
@pytest.mark.freeze_time("2022-08-24")
def test_request_client__upload_request__success(
    mocker: MockerFixture,
    mock_upload_s3_obj,
    mock_make_bucket,
    mock_s3_client,
    retry,
    prefix,
    expected_result,
):
    mock_make_bucket("qa")
    mocker.patch(
        "cli.parameter_store.requests_client.upload_s3_obj", mock_upload_s3_obj
    )
    request: RequestType = {
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
        "reviewer": None,
        "reviewed_at": None,
    }
    with expected_result:
        key, bucket = RequestsClient.upload_request(
            env="qa", request=request, prefix=prefix, retry=retry
        )
        # the following assertions are only made if expected_result was does_not_raise() because if upload_request
        # raises exception the test ends
        assert prefix in key
        if retry:
            assert f"/{request['touches']}/" in key
        response = mock_s3_client.get_object(Key=key, Bucket=bucket)
        content = json.load(response["Body"])
        assert content == request
