from datetime import datetime
from typing import Optional

from botocore.exceptions import ClientError

from cli.constants import ENV_TO_AWS_ACCOUNT, ENVIRONMENTS
from cli.parameter_store.exceptions import (
    InsufficientPermissionException,
    InvalidParameterPathError,
    NonExistentParameterPathError,
    Permissions,
    StaleCredentialsError,
    devCliException,
)


def get_bucket_name(env: str):
    if not env:
        raise devCliException("Error: get_bucket_name called with no env")
    return f"{env}-dev-useast2-dev-tools-param-requests"


def get_queue_name(env: str):
    if not env:
        raise devCliException("Error: get_queue_name called with no env")
    return f"{env}-dev-useast2-dev-tools-review"


def get_queue_url(env: str):
    account_id = ENV_TO_AWS_ACCOUNT[env]
    return f"https://sqs.us-east-2.amazonaws.com/{account_id}/{get_queue_name(env)}"


def get_env(path):
    env = None
    for _env in ENVIRONMENTS:
        if path.startswith(f"/{_env}/"):
            env = _env
    if not env:
        raise InvalidParameterPathError(
            "Parameter path must start with an environment, e.g., `/qa`."
        )
    return env


def transform_client_error(
    error: ClientError, env, path=None, action: Optional[Permissions] = None
):
    if error.response["Error"]["Code"] == "ParameterNotFound":
        return NonExistentParameterPathError(
            f'Parameter path "{path}" does not exist in {env}. The path should be created via'
            + " terraform. Please submit an infra PR to create it before requesting its value be set"
        )
    if error.response["Error"]["Code"] in [
        "ExpiredToken",
        "ExpiredTokenException",
    ]:
        return StaleCredentialsError(
            f"Your AWS credentials for {env} are stale. Please refresh and/or check your configuration"
        )
    if error.response["Error"]["Code"] in [
        "NotAuthorized",
        "AccessDenied",
        "AccessDeniedException",
    ]:
        return InsufficientPermissionException(
            f"You lack permission to {action} in {env}. Please contact the SRE team for assistance"
        )
    return devCliException(f"{error}")


def iso_datetime(dt: Optional[datetime] = None):
    if not dt:
        dt = datetime.utcnow()
    return dt.isoformat()


def filename_from_obj(request):
    requested_at = parse_datetime_string(request["requested_at"]).strftime(
        "%Y.%m.%d-%H.%M.%S"
    )
    return f"{requested_at}-{request['id']}.json"


def parse_datetime_string(datetime_str):
    try:
        return datetime.fromisoformat(datetime_str)
    except ValueError:
        try:
            return datetime.strptime(datetime_str, "%Y.%m.%d-%H%.M%.S")
        except ValueError:
            return datetime.strptime(datetime_str, "%Y%m%d-%H%M%S")
