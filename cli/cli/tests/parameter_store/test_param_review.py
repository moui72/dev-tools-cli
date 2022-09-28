from unittest.mock import ANY

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from cli.main import app
from cli.parameter_store.exceptions import (
    InsufficientPermissionException,
    MalformedSQSMessageError,
    NoMessagesInReviewQueue,
    Retry,
)
from cli.parameter_store.types import DecisionResponse
from cli.constants import ReviewableEnv

REVIEW_COMMAND = ["params", "review"]


@pytest.mark.freeze_time("2022-08-24")
@pytest.mark.parametrize(
    "env,decision",
    [
        ("qa", "approve"),
        ("qa", "reject"),
        ("qa", "defer"),
    ],
)
def test_param_review__success(
    mocker: MockerFixture,
    env,
    mock_put_request,
    decision,
    mock_all_aws,
    mock_aws_config,
):
    mocker.patch(
        "cli.parameter_store.actions.get_user_for_env",
        return_value="TEST@testing.com",
    )
    mocker.patch("cli.parameter_store.main.typer.prompt", return_value=decision)
    mocker.patch("cli.parameter_store.main.typer.confirm", return_value=True)
    mock_do = mocker.patch("cli.parameter_store.main.do")
    mock_delete_sqs_message = mocker.patch(
        "cli.parameter_store.requests_client.delete_sqs_message"
    )
    filename, _, request, _ = mock_put_request(env)
    runner = CliRunner()
    result = runner.invoke(app, REVIEW_COMMAND + [env])

    assert result.exit_code == 0
    expected_request = request.copy()
    if decision != DecisionResponse.DEFER:
        expected_request["reviewer"] = "TEST@testing.com"
        expected_request["reviewed_at"] = "2022-08-24T00:00:00"
    expected_request["touches"] = 1

    mock_delete_sqs_message.assert_called_once_with(env="qa", handle=ANY)
    mock_do.assert_called_once_with(
        env=ReviewableEnv(env),
        action=decision,
        request=expected_request,
        original_key=filename,
    )


@pytest.mark.freeze_time("2022-08-24")
@pytest.mark.parametrize(
    "env,exception,called,expected_exit_code",
    [
        (
            "qa",
            MalformedSQSMessageError,
            "cli.parameter_store.requests_client.delete_sqs_message",
            0,
        ),
        ("qa", NoMessagesInReviewQueue, None, 0),
        (
            "qa",
            ValueError,
            "cli.parameter_store.requests_client.restore_sqs_message",
            1,
        ),
    ],
)
def test_param_review__error_on_process_sqs_message__restore_or_delete_sqs_message(
    mocker: MockerFixture,
    mock_put_request,
    mock_all_aws,
    env,
    exception,
    called,
    expected_exit_code,
):
    mocker.patch(
        "cli.parameter_store.requests_client.process_sqs_message",
        side_effect=exception("explicit raise in test"),
    )
    if called:
        mocked_called = mocker.patch(called)
    mock_put_request(env)
    runner = CliRunner()
    result = runner.invoke(app, REVIEW_COMMAND + [env])
    if called:
        mocked_called.assert_called_once_with(env=env, handle=ANY)
    assert result.exit_code == expected_exit_code


@pytest.mark.parametrize(
    "env,exception",
    [
        ("qa", InsufficientPermissionException),
        ("qa", ValueError),
    ],
)
def test_param_review__error_on_do__restore_sqs_message(
    mocker: MockerFixture,
    mock_put_request,
    mock_all_aws,
    env,
    exception,
):
    mocker.patch(
        "cli.parameter_store.main.do",
        side_effect=exception("explicit raise in test"),
    )
    mocked_called = mocker.patch(
        "cli.parameter_store.requests_client.restore_sqs_message"
    )
    mock_put_request(env)
    runner = CliRunner()
    result = runner.invoke(app, REVIEW_COMMAND + [env])
    mocked_called.assert_called_once_with(env=env, handle=ANY)
    assert result.exit_code > 0


def test_param_review__retry(
    mocker: MockerFixture,
    mock_put_request,
    mock_all_aws,
):
    env = "qa"
    mocker.patch(
        "cli.parameter_store.requests_client.RequestsClient.fetch_s3_object_from_sqs_message",
        side_effect=(Retry, NoMessagesInReviewQueue),
    )
    mocked_restore = mocker.patch(
        "cli.parameter_store.requests_client.restore_sqs_message"
    )
    mocked_delete = mocker.patch(
        "cli.parameter_store.requests_client.restore_sqs_message"
    )
    mock_put_request(env)
    runner = CliRunner()
    result = runner.invoke(app, REVIEW_COMMAND + [env])
    mocked_restore.assert_not_called()
    mocked_delete.assert_called_once_with(env=env, handle=ANY)
    assert result.exit_code == 0
