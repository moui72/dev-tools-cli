import logging
from typing import Optional

import typer
from botocore.exceptions import ClientError
from rich import print
from rich.console import Console

from cli.constants import GLOBAL_RICH_CONSOLE_THEME, ReviewableEnv
from cli.parameter_store.actions import (
    do,
    format_request,
    make_request,
    update_request_on_review,
)
from cli.parameter_store.exceptions import (
    DevCliException,
    InsufficientPermissionException,
    InvalidParameterPathError,
    NoMessagesInReviewQueue,
    Permissions,
    Retry,
    StaleCredentialsError,
)
from cli.parameter_store.requests_client import RequestsClient as rq
from cli.parameter_store.requests_client import next_sqs_message
from cli.parameter_store.types import DecisionResponse, RequestType
from cli.parameter_store.utils import get_env, transform_client_error
from cli.parameter_store.validate import validate_param_exists, validate_param_name
from cli.services.aws.exceptions import NoValidProfileError

app = typer.Typer()

NoteOption = typer.Option(
    (None, None),
    "--note",
    "-n",
    help="A note to attach to the request. Two values are accepted: the first is the subject and the second"
    + " is the body of the note.",
    show_default=False,
)
EncryptOption = typer.Option(True, "--encrypt/--no-encrypt", "-e/-n")


@app.command()
def request(
    path: str,
    value: str,
    encrypt: bool = EncryptOption,
    note: Optional[tuple[str, str]] = NoteOption,
):
    """Creates a new request to change the value of PATH to VALUE"""
    env = get_env(path)

    try:
        validate_param_exists(env=env, path=path)
    except InsufficientPermissionException as ipe:
        try:
            validate_param_name(path)
        except InvalidParameterPathError as e:
            print(e)
            raise typer.Exit(1)
        else:
            print(
                f"Warning: {ipe}. The request will continue, but may be rejected if the parameter doesn't exist."
                + " Parameters should be created in terraform. This tool is for setting values on existing parameters."
            )
    except DevCliException as e:
        print(f"{e}")
        raise typer.Exit(1)
    except NoValidProfileError:
        print("Something is wrong with your AWS config. Try dev sso config --help")
        raise typer.Exit(2)
    except Exception as e:
        print(f"{e}. Could not verify that the specified parameter exists")
        raise typer.Exit(2)

    body: RequestType = make_request(
        env=env,
        path=path,
        value=value,
        encrypt=encrypt,
        note=note,
    )
    try:
        key, _ = rq.upload_request(request=body, env=env)
    except ClientError as e:
        logging.debug(f"{e}")
        raise transform_client_error(e, env=env, action=Permissions.WRITE_S3)
    else:
        print(f"Success: Submitted request {body['id']}")
        console = Console(theme=GLOBAL_RICH_CONSOLE_THEME)
        console.print(format_request(request=body, key=key, env=env))
        return True


@app.command()
def review(environment: ReviewableEnv):
    """Approve or reject requests for a given environment (i.e., `dev`, `qa`, `stage`, or `prod`)"""
    try:
        with next_sqs_message(env=environment) as message:
            try:
                param_request, key = rq.fetch_s3_object_from_sqs_message(
                    env=environment, message=message
                )
            except ClientError as e:
                raise transform_client_error(
                    error=e, env=environment, action=Permissions.RECEIVE_SQS
                )
            param_request["touches"] += 1
            console = Console(theme=GLOBAL_RICH_CONSOLE_THEME)
            console.print(
                format_request(request=param_request, key=key, env=environment)
            )
            request_id = param_request["id"]
            confirmed = False
            while not confirmed:
                action = typer.prompt(
                    "Would you like to [a]pprove, [r]eject, or [D]efer?",
                    type=DecisionResponse,
                    default=DecisionResponse.DEFER,
                    show_choices=False,
                    show_default=False,
                )
                if action in ["approve", "reject"]:
                    confirmed = typer.confirm(
                        f"Are you sure you want to {action} this request?"
                    )
                else:
                    confirmed = True
            if action != DecisionResponse.DEFER:
                param_request = update_request_on_review(
                    env=environment, request=param_request
                )

            do(
                env=environment,
                action=action,
                request=param_request,
                original_key=key,
            )
            print(f"Success: You selected {action} for {request_id}")

        return True
    except NoMessagesInReviewQueue:
        print(
            f":sparkles: Review queue for {environment} is empty, nothing needs doing"
        )
        raise typer.Exit()
    except Retry:
        return review(environment=environment)
    except InsufficientPermissionException:
        print(
            f"You don't have permission to review. If that doesn't seem right, please consult with SRE."
        )
        raise typer.Exit(3)
    except StaleCredentialsError:
        print(
            f"Could not start review process, your credentials appear to be expired. Please refresh"
            + " your credentials and try again."
        )
        raise typer.Exit(1)
