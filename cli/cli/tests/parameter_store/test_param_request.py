import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from cli.main import app
from cli.parameter_store.utils import get_bucket_name

REQUEST_CMD = ["params", "request"]


@pytest.mark.parametrize(
    "args",
    [
        ["/qa/abc", "def", "-n", "please", "i really need it"],
        ["/qa/abc", "def"],
    ],
)
def test__param_request_create_cli_integration__param_not_found(
    mocker: MockerFixture, args, mock_all_aws
):
    mocker.patch(
        "cli.parameter_store.validate.get_parameter",
        side_effect=ClientError(
            error_response={"Error": {"Code": "ParameterNotFound", "Status": 404}},
            operation_name="TEST",
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, REQUEST_CMD + args)
    assert result.output.replace("\n", " ").replace("  ", " ").strip() == (
        'Parameter path "/qa/abc" does not exist in qa. The path should be created via terraform. Please submit an'
        + " infra PR to create it before requesting its value be set"
    )
    assert result.exit_code > 0


@pytest.mark.parametrize(
    "args",
    [
        ["/qa/abc", "def", "-n", "please", "i really need it"],
        ["/qa/abc", "def"],
    ],
)
def test__param_request_create__invoke__success(
    mocker: MockerFixture,
    args: list[str],
    mock_s3_client,
    mock_ssm_client,
    mock_all_aws,
):
    mocker.patch(
        "cli.parameter_store.actions.get_user_for_env",
        return_value="TEST@testing.com",
    )
    region = "us-east-2"
    mock_s3_client.create_bucket(
        Bucket=get_bucket_name(env="qa"),
        CreateBucketConfiguration={"LocationConstraint": region},
    )
    mock_ssm_client.put_parameter(Name=args[0], Value="initial")
    runner = CliRunner()
    result = runner.invoke(app, REQUEST_CMD + args)
    obj = mock_s3_client.list_objects(Bucket=get_bucket_name(env="qa"))
    assert len(obj["Contents"]) == 1
    assert obj["Contents"][0]["Key"].startswith("requested/")
    assert result.exit_code == 0
