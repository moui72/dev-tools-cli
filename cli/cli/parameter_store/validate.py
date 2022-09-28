from re import fullmatch

from botocore.exceptions import ClientError

from cli.parameter_store.exceptions import InvalidParameterPathError, Permissions
from cli.parameter_store.utils import get_env, transform_client_error
from cli.services.aws.clients_service import get_parameter


def validate_param_exists(env, path: str):
    try:
        get_parameter(env, path)
    except ClientError as e:
        raise transform_client_error(e, env=env, path=path, action=Permissions.READ_SSM)
    return True


def validate_param_name(path: str):
    get_env(path)
    if len(path) < 1 or len(path) > 2048:
        raise InvalidParameterPathError(
            "Parameter name must be between 1 and 2048 characters long"
        )
    if path.count("/") > 15:
        raise InvalidParameterPathError(
            "Parameter hierarchies are limited to a maximum depth of fifteen levels."
        )
    if not fullmatch(r"[a-zA-Z0-9_./-]+", path):
        raise InvalidParameterPathError(
            "Parameter name can only contain alphanumeric characters, underscores, hyphens, or periods."
        )
    return True
