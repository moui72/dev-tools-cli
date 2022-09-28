import pytest
from botocore.exceptions import ClientError
from moto import mock_ssm
from pytest_mock import MockerFixture

from cli.parameter_store.exceptions import (
    InsufficientPermissionException,
    InvalidParameterPathError,
    NonExistentParameterPathError,
    StaleCredentialsError,
)
from cli.parameter_store.validate import validate_param_exists, validate_param_name


@mock_ssm
def test_validate_param_not_exists__raises(mocker):
    mocker.patch(
        "cli.parameter_store.validate.get_parameter",
        side_effect=ClientError(
            error_response={"Error": {"Code": "ParameterNotFound", "Status": 404}},
            operation_name="TEST",
        ),
    )
    with pytest.raises(NonExistentParameterPathError):
        validate_param_exists("qa", "qa/abc")


@mock_ssm
def test_validate_param_exists__True(mocker):
    mocker.patch("cli.parameter_store.validate.get_parameter")
    assert validate_param_exists(env="qa", path="qa/abc") is True


@pytest.mark.parametrize(
    "client_error,raised_exception",
    [
        (
            ClientError(
                error_response={
                    "Error": {"Code": "ExpiredTokenException", "Status": 403}
                },
                operation_name="TEST",
            ),
            StaleCredentialsError,
        ),
        (
            ClientError(
                error_response={
                    "Error": {"Code": "AccessDeniedException", "Status": 403}
                },
                operation_name="TEST",
            ),
            InsufficientPermissionException,
        ),
    ],
)
def test_validate_param_exists__raises(
    mocker: MockerFixture, client_error, raised_exception
):
    mocker.patch("cli.parameter_store.validate.get_parameter", side_effect=client_error)
    with pytest.raises(raised_exception):
        validate_param_exists("qa", "abc")


@pytest.mark.parametrize(
    "valid_path",
    [
        "/qa/asd",
        "/qa/asd/fgh/jkl",
        "/dev/asd-asd",
        "/stage/asd-123",
        "/prod/asd-123.asd",
    ],
)
def test_validate_param_name__success(valid_path):
    assert validate_param_name(valid_path) is True


@pytest.mark.parametrize(
    "invalid_path,expected_message",
    [
        (
            "/local/asd",
            "Parameter path must start with an environment, e.g., `/qa`.",
        ),
        (
            "asd",
            "Parameter path must start with an environment, e.g., `/qa`.",
        ),
        (
            "",
            "Parameter name must be between 1 and 2048 characters long",
        ),
        (
            "/qa/" + "long" * 512,
            "Parameter name must be between 1 and 2048 characters long",
        ),
        (
            "/qa/" + "long" * 512,
            "Parameter name must be between 1 and 2048 characters long",
        ),
        (
            "/qa/" * 20,
            "Parameter hierarchies are limited to a maximum depth of fifteen levels.",
        ),
        (
            "/qa/asd+asd-as" * 20,
            "Parameter name can only contain alphanumeric characters, underscores, hyphens, or periods.",
        ),
    ],
)
def test_validate_param_name__raises(invalid_path, expected_message):
    with pytest.raises(InvalidParameterPathError) as e:
        validate_param_name("/local/asd")
        assert f"{e}" == expected_message
