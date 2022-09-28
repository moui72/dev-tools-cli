import logging
from datetime import datetime
from typing import Optional, Union
from uuid import uuid4

import click
from botocore.exceptions import ClientError
from dateutil.parser import isoparse
from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from cli.parameter_store.exceptions import NoteDisplayException, Permissions
from cli.parameter_store.requests_client import RequestsClient as rq
from cli.parameter_store.types import (
    DecisionResponse,
    EnvDisplay,
    NoteType,
    RequestType,
)
from cli.parameter_store.utils import (
    get_env,
    iso_datetime,
    parse_datetime_string,
    transform_client_error,
)
from cli.services.aws.clients_service import get_user_for_env


def format_datetime(dt: Union[datetime, str]):
    _dt = isoparse(dt) if isinstance(dt, str) else dt
    return _dt.strftime("%B %d, %Y at %H:%M")


def format_note(author, added, subject, body):
    if not subject and not body:
        raise NoteDisplayException("Empty note")
    subtitle = f"{format_datetime(added)}"
    title = f"[cyan]{author}[/]"
    if body:
        if subject:
            title = f'"{subject}" from {title}'
        output = body
    else:
        output = subject
    return Panel(
        output,
        title=title,
        subtitle=subtitle,
        title_align="left",
        subtitle_align="right",
    )


def format_request(request: RequestType, key: str, env: str):
    renderables: list[RenderableType] = []
    request_details = Table(
        title=f"{EnvDisplay(env)} Parameter Change Request",
        caption=f"s3 key: {key}",
        expand=True,
        box=box.ROUNDED,
        caption_style="subtle",
        title_style="bold",
    )
    request_details.add_column(
        "Field", justify="right", no_wrap=True, ratio=1, style="subtle"
    )
    request_details.add_column("Value", ratio=2)
    mask_value = request["encrypt"]

    notes = request["notes"]
    for k, v in request.items():
        if k == "notes":
            continue
        if k == "value" and mask_value:
            value = "*" * min(len(v), 10)  # type: ignore[arg-type]
        elif "_at" in k and v:
            value = format_datetime(parse_datetime_string(v))
        else:
            value = str(v)  # type: ignore[assignment]
        request_details.add_row(k, value)
    renderables.append(request_details)
    notes_display = []
    if notes:
        for note in notes:
            try:
                notes_display.append(format_note(**note))
            except TypeError:
                pass
            except NoteDisplayException:
                pass
    if notes_display:
        renderables.append(Panel(Group(*notes_display), title="Notes"))
    return Group(*renderables)


def update_request_on_review(env, request: RequestType):
    request["reviewer"] = get_user_for_env(env)
    request["reviewed_at"] = iso_datetime()
    return request


def make_request(env, path, value, encrypt, note) -> RequestType:
    return {
        "path": path,
        "value": value,
        "encrypt": encrypt,
        "requester": get_user_for_env(env),
        "requested_at": iso_datetime(),
        "touches": 0,
        "reviewer": None,
        "reviewed_at": None,
        "notes": [make_note(env, note or ("", ""))],
        "id": str(uuid4()),
    }


def make_note(env, note: tuple[str, str]) -> NoteType:
    return {
        "author": get_user_for_env(env),
        "subject": note[0],
        "body": note[1],
        "added": iso_datetime(),
    }


def prompt_for_note():
    if click.confirm("Would you like to add a note?", default=False):
        subject: str = ""
        body: str = ""
        while not subject:
            subject = click.prompt("Subject: ", type=str)
        body = click.prompt("Body: ", type=str)
        return subject, body
    else:
        return None


def do(
    env: str,
    action: DecisionResponse,
    request: RequestType,
    original_key: Optional[str],
):
    if action in ("approve", "reject", "defer"):
        raw_note = prompt_for_note()
        if raw_note:
            request["notes"].append(
                make_note(env=get_env(request["path"]), note=raw_note)
            )
    try:
        if action == DecisionResponse.APPROVE:
            rq.upload_request(env, request=request, prefix="approved")
        elif action == DecisionResponse.REJECT:
            rq.upload_request(env, request=request, prefix="rejected")
        else:
            rq.upload_request(
                env, request=request, prefix=f"requested/{action}-{request['touches']}"
            )
    except ClientError as e:
        raise transform_client_error(error=e, env=env, action=Permissions.WRITE_S3)
    try:
        if original_key:
            rq.delete_request(env=env, key=original_key)
        else:
            logging.debug(
                "Could not delete original S3 object because the original key could not be retrieved"
            )
    except ClientError as e:
        raise transform_client_error(error=e, env=env, action=Permissions.WRITE_S3)
