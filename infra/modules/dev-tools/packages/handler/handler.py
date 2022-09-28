import json
from os import environ
import logging
import enum
from typing import Optional, Union
from dateutil.parser import isoparse
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
import requests

from local_types import (
    SQSMessageType,
    SQSRecordType,
    ParamRequest,
    S3RecordType,
    NoteType,
)
from exceptions import EmptyNoteException

ACTIONS = ["requested", "rejected", "approved"]
S3 = boto3.client("s3")
SSM = boto3.client("ssm")
SLACK_CHANNEL = environ.get("SLACK_NOTIFICATION_CHANNEL")
LOG = logging.getLogger()
LOG.setLevel(logging.DEBUG)
logging.debug(logging.root.manager.loggerDict)


class ParamType(str, enum.Enum):
    String = "String"
    SecureString = "SecureString"


def load_object(bucket: str, key: str) -> ParamRequest:
    logging.info(f"Loading {key} from {bucket}")
    response = S3.get_object(Bucket=bucket, Key=key)
    content: ParamRequest = json.load(response["Body"])
    return content


def send_slack_message(payload: dict[str, str]):
    if SLACK_CHANNEL:
        logging.info(f"Sending slack message: {payload['text']}")
        r = requests.post(SLACK_CHANNEL, json=payload)
        logging.debug(r)
    else:
        logging.info(f"No channel for slack message: {payload['text']}")


def update_parameter(path: str, value: str, type: ParamType):
    display_value = value if "Secure" not in type else "***"
    logging.info(f"Updating {path} ({type}) to {display_value}")
    r = SSM.put_parameter(
        Name=path,
        Value=value,
        Type=type,
        Overwrite=True,
    )
    logging.debug(r)


def move_object(bucket: str, original_key: str, new_key: str):
    logging.info(f"Moving {original_key} to {new_key} in {bucket}")
    S3.copy_object(
        Bucket=bucket, Key=new_key, CopySource={"Bucket": bucket, "Key": original_key}
    )
    S3.delete_object(Bucket=bucket, Key=original_key)


def split_key(full_key):
    key_parts = full_key.split("/")
    return key_parts[0], "/".join(key_parts[1:])


def make_slack_payload(
    action: str,
    path: str,
    encrypt: bool,
    value: str,
    notes: list[NoteType],
    requester: str,
    reviewer: str,
    requested_at: str,
    reviewed_at: str,
):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Parameter store value change for {path} has been {action}.\n",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Requested at:*\n{requested_at}"},
                {"type": "mrkdwn", "text": f"*Requested by:*\n{requester}"},
            ],
        },
    ]
    if reviewer:
        blocks += [
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Reviewed at:*\n{reviewed_at}"},
                    {"type": "mrkdwn", "text": f"*Reviewed by:*\n{reviewer}"},
                ],
            },
        ]
    attachments = []
    for note in notes:
        try:
            attachments.append(make_note_block(**note))
        except EmptyNoteException:
            continue
    if attachments:
        blocks += [
            {"type": "divider"},
            {
                "type": "context",
                "fields": [
                    {
                        "type": "plain_text",
                        "text": f"There are {len(attachments)} notes attached to this request",
                    },
                ],
            },
        ]
    return {"blocks": blocks, "attachments": attachments}


def dt_string_to_ts(dt: Union[datetime, str]):
    _dt = isoparse(dt) if isinstance(dt, str) else dt
    return int(_dt.timestamp())


def make_note_block(
    author: str,
    added: str,
    subject: Optional[str],
    body: Optional[str],
) -> dict[str, Union[int, str, None]]:
    if not subject and not body:
        raise EmptyNoteException()

    if not body:
        body = subject
        subject = None

    return {
        "title": subject or "(no subject)",
        "author": author,
        "text": body,
        "ts": dt_string_to_ts(added),
        "fallback": subject or body,
    }


def handle(event: SQSMessageType, ctx):
    logging.debug(event)
    logging.debug(ctx)
    record: SQSRecordType = event["Records"][0]
    s3_notification: S3RecordType = json.loads(record["body"])["Records"][0]

    bucket = s3_notification["s3"]["bucket"]["name"]
    full_key = s3_notification["s3"]["object"]["key"]
    key_prefix, key_suffix = split_key(full_key)
    if key_prefix not in ACTIONS:
        logging.warning(
            f"Discarding message, {key_prefix} is not a valid action (s3 path: {key_suffix})"
        )
        return False
    else:
        logging.info(
            f"Processing parameter store value change {key_prefix} for s3 path {key_suffix}"
        )
    resulted = key_prefix
    content = load_object(bucket=bucket, key=full_key)
    review_text = f'\n- Reviewed by {content["reviewer"]} at {content["reviewed_at"]}.'
    if key_prefix == "approved":
        try:
            update_parameter(
                path=content["path"],
                value=content["value"],
                type=ParamType(f"{'Secure' if content['encrypt'] else ''}String"),
            )
        except ClientError as e:
            slack_message = {
                "text": f':warning: Parameter store value change for {content["path"]} was approved, but lambda failed'
                + f" to update the value: {e}\n"
                + f'\n- Requested by {content["requester"]} at {content["requested_at"]}.'
                + review_text
                + f"\n\n ATTN: @sre please address this!"
            }
            send_slack_message(payload=slack_message)
            raise e
        resulted = "approved and changed via devops-tools :meow_ok:"
    elif key_prefix == "rejected":
        resulted = f"{key_prefix} :meow_no:"
        review_text = (
            f'\n- Reviewed by {content["reviewer"]} at {content["reviewed_at"]}.'
        )
    elif key_prefix == "requested":
        resulted = f"{key_prefix} :meow_peek:"
        review_text = "\n\nATTN: @sre please review"
        review_key = f"review/{key_suffix}"
        move_object(bucket, original_key=full_key, new_key=review_key)
    resulted = resulted or "touched"
    slack_message = {
        "text": f'Parameter store value change for {content["path"]} has been {resulted}.\n'
        + f'\n- Requested by {content["requester"]} at {content["requested_at"]}.'
        + review_text
    }
    send_slack_message(payload=slack_message)
    return True
