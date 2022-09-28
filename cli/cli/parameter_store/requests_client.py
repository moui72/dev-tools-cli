import json
import logging
from contextlib import AbstractContextManager
from io import BytesIO

from botocore.exceptions import ClientError

from cli.parameter_store.exceptions import (
    DiscardMessageException,
    ErrorAfterSQSMessageReceived,
    MalformedS3ObjectError,
    MalformedSQSMessageError,
    MissingS3ObjectError,
    NoMessagesInReviewQueue,
    Retry,
    RetryReviewNotAllowed,
)
from cli.parameter_store.types import RequestType
from cli.parameter_store.utils import (
    filename_from_obj,
    get_bucket_name,
    get_queue_url,
)
from cli.services.aws.clients_service import (
    delete_s3_obj,
    delete_sqs_message,
    get_s3_obj,
    process_sqs_message,
    receive_sqs_message,
    restore_sqs_message,
    upload_s3_obj,
)


class next_sqs_message(AbstractContextManager):
    def __init__(self, env):
        self.env = env
        self.response = None
        self.messages = None

    def __enter__(self):
        queue_url = get_queue_url(self.env)
        logging.debug(f"QUEUE_URL: {queue_url}")
        self.response = receive_sqs_message(queue_url=queue_url, env=self.env)
        try:
            self.messages = self.response["Messages"]
        except KeyError:
            raise NoMessagesInReviewQueue()
        return self.response

    def __exit__(self, __exc_type, __exc_value, __traceback):
        if isinstance(__exc_value, DiscardMessageException) or __exc_type is None:
            for message in self.messages:
                print("Deleting bad SQS message")
                logging.debug(message)
                delete_sqs_message(env=self.env, handle=message["ReceiptHandle"])
            if isinstance(__exc_value, MalformedS3ObjectError):
                key = __exc_value.record["s3"]["object"]["key"]
                print(f"Deleting bad S3 object ({key})")
                logging.debug(__exc_value.record)
                RequestsClient.delete_request(env=self.env, key=key)
            if __exc_type is not None:
                print(f"Retrying")
                raise Retry()
        else:
            for message in self.messages:
                print("Restoring SQS message")
                restore_sqs_message(env=self.env, handle=message["ReceiptHandle"])
        return super().__exit__(__exc_type, __exc_value, __traceback)


class RequestsClient:
    @staticmethod
    def fetch_s3_object_from_sqs_message(env: str, message) -> tuple[RequestType, str]:
        record = process_sqs_message(env=env, message=message)
        try:
            key = record["s3"]["object"]["key"]
        except Exception as e:
            print("error accessing s3 object key")
            raise MalformedSQSMessageError(
                "Record is missing critical fields", event=e, record=record
            ) from e
        try:
            response = get_s3_obj(env=env, key=key)
        except ClientError as e:
            print("error loading object from s3")
            logging.debug(record)
            logging.debug(e)
            if e.response["Error"]["Code"] == "NoSuchKey":
                message = f"Recieved SQS message that corresponds to deleted/missing S3 object (key={key})"
                logging.debug(message)
                raise MissingS3ObjectError(message)
            else:
                raise ErrorAfterSQSMessageReceived(
                    message="Error fetching object from S3",
                    event=e,
                    record=record,
                ) from e
        try:
            content: RequestType = json.load(response["Body"])
        except Exception as e:
            print("Error parsing json from s3")
            print(e)
            raise MalformedS3ObjectError(
                "Record is missing critical fields",
                event=e,
                record=record,
            ) from e
        return content, key

    @staticmethod
    def delete_request(env: str, key: str):
        return delete_s3_obj(bucket=get_bucket_name(env=env), key=key, env=env)

    @staticmethod
    def upload_request(
        env: str,
        request: RequestType,
        prefix="requested",
        retry=False,
    ):
        if retry:
            if prefix != "requested":
                raise RetryReviewNotAllowed(
                    "Attempted to retry upload of reviewed request. This shouldn't happen",
                )
            prefix += f"/{request['touches']}/"
        obj = BytesIO(initial_bytes=json.dumps(request).encode("utf-8"))
        filename = filename_from_obj(request)
        key = f"{prefix}/{filename}"
        resp = upload_s3_obj(
            obj, bucket=get_bucket_name(env=env), key=f"{prefix}/{filename}", env=env
        )
        logging.debug(f"Uploaded request to {prefix}/{filename}\n\n{request}\n\n{resp}")
        return key, get_bucket_name(env=env)
