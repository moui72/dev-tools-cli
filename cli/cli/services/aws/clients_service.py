import json
import logging
from abc import ABC

import boto3
from botocore.client import BaseClient
from botocore.exceptions import UnknownServiceError

from cli.constants import AWS_DEFAULT_REGION, AWS_SSO_REGION_KEY, ENVIRONMENTS
from cli.parameter_store.exceptions import (
    MalformedSQSMessageError,
    NoMessagesInReviewQueue,
)
from cli.parameter_store.types import RecordType
from cli.parameter_store.utils import get_bucket_name, get_queue_url
from cli.services.aws.config_service import AWS_CFG


def get_user_for_env(env: str):
    raw_user: str = aws[env].sts.get_caller_identity()["UserId"]
    _role, email = raw_user.split(":")
    return email


def restore_sqs_message(env, handle):
    queue_url = get_queue_url(env)
    response = aws[env].sqs.change_message_visibility(
        QueueUrl=queue_url,
        ReceiptHandle=handle,
        VisibilityTimeout=0,
    )
    return response


def delete_sqs_message(env, handle):
    queue_url = get_queue_url(env)
    response = aws[env].sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=handle,
    )
    return response


def receive_sqs_message(env=None, queue_url=None):
    queue_url = queue_url or get_queue_url(env)
    return aws[env].sqs.receive_message(QueueUrl=queue_url)


def process_sqs_message(env: str, message):
    if "Messages" not in message:
        print("No messages in queue")
        logging.debug(message)
        raise NoMessagesInReviewQueue()
    try:
        event = json.loads(message["Messages"][0]["Body"])
    except Exception as e:
        print("error loading event")
        raise MalformedSQSMessageError(
            message="Failed to parse SQS message body"
        ) from e
    try:
        record: RecordType = event["Records"][0]
    except (KeyError, IndexError) as e:
        print("error loading record")
        raise MalformedSQSMessageError(
            message=f"SQS message was parsed but appears malformed: {e.__class__.__name__}: {e}",
            event=event,
        ) from e
    return record


def send_sqs_message(env: str, message: str):
    queue_url = get_queue_url(env)
    logging.debug(f"QUEUE_URL: {queue_url}")
    resp = aws[env].sqs.send_message(QueueUrl=queue_url, MessageBody=message)
    return resp


def get_parameter(env: str, path: str):
    return aws[env].ssm.get_parameter(Name=path)


def upload_s3_obj(obj, key, env, bucket=None):
    bucket = bucket or get_bucket_name(env=env)
    return aws[env].s3.upload_fileobj(obj, Bucket=bucket, Key=key)


def get_s3_obj(key, env, bucket=None) -> str:
    bucket = bucket or get_bucket_name(env=env)
    return aws[env].s3.get_object(Bucket=bucket, Key=key)


def delete_s3_obj(key, env, bucket=None):
    bucket = bucket or get_bucket_name(env=env)
    return aws[env].s3.delete_object(Bucket=bucket, Key=key)


class ClientInterface(ABC):

    env: str

    def sqs(self):
        raise NotImplementedError

    def ssm(self):
        raise NotImplementedError

    def s3(self):
        raise NotImplementedError


class AWSClientManager(ClientInterface):
    _clients: dict[str, BaseClient] = {}

    def __init__(self, env):
        self.env = env
        self.profile_name = AWS_CFG.get_profile_name_for_env(env).split(" ").pop()
        self.profile = AWS_CFG.profiles[AWS_CFG.get_profile_name_for_env(env)]
        self.region = self.profile.get(
            "region", self.profile.get(AWS_SSO_REGION_KEY, AWS_DEFAULT_REGION)
        )
        self.session = boto3.Session(profile_name=self.profile_name)

    def _new_client(self, service):
        if service not in self._clients:
            logging.debug(f"Creating new client for {service} in {self.env}")
            region = self.profile.get("sso_region", self.profile.get("region"))
            new_client = self.session.client(service, region_name=region)
            self._clients[service] = new_client
        else:
            logging.debug(f"Client for {service} in {self.env} already exists")
        return self._clients[service]

    def __getattribute__(self, name: str):
        logging.debug(f"Getting AWSClientManager().{name}")
        if name in boto3.Session().get_available_services():
            error_message = f"Could not get client for {name}."
            try:
                object.__getattribute__(self, "_new_client")(name)
            except UnknownServiceError as e:
                raise AttributeError(error_message + " Not a valid service.") from e
            except Exception as e:
                raise AttributeError(error_message) from e
            return object.__getattribute__(self, "_clients")[name]
        return object.__getattribute__(self, name)


class EnvManager:
    _client_managers: dict[str, BaseClient] = {}

    def _new_client_manager(self, env):
        if env not in self._client_managers:
            logging.debug(f"Creating new client manager for {env}")
            new_client_manager = AWSClientManager(env)
            self._client_managers[env] = new_client_manager
        else:
            logging.debug(f"Client manager for {env} already exists")
        return self._client_managers[env]

    def __getitem__(self, key: str):
        logging.debug(f"Getting EnvManager[{key}]")
        if key not in ENVIRONMENTS:
            raise KeyError(f"`{key}` is not a supported environment")
        if key not in self._client_managers:
            return self._new_client_manager(key)
        return self._client_managers[key]


aws = EnvManager()
