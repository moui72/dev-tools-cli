import enum
from typing import Optional

from cli.parameter_store.types import RecordType


class Permissions(str, enum.Enum):
    WRITE_S3 = "write to the relevant S3 bucket"
    READ_SSM = "read parameters"
    RECEIVE_SQS = "receive messages from the relevant SQS queue"


class DevCliException(Exception):
    """Not all exceptions are fatal"""

    pass


class Retry(DevCliException):
    """Retry the command"""


class NoteDisplayException(DevCliException):
    pass


class InsufficientPermissionException(DevCliException):
    pass


class ParameterNotFoundException(DevCliException):
    pass


class NoMessagesInReviewQueue(DevCliException):
    pass


class devCliError(DevCliException):
    """All errors are fatal"""

    pass


class StaleCredentialsError(devCliError):
    pass


class InvalidParameterPathError(devCliError):
    pass


class NonExistentParameterPathError(devCliError):
    pass


class ErrorAfterSQSMessageReceived(devCliError):
    def __init__(self, message, event=None, record=None):
        super().__init__(message)
        self.event = event
        self.record: Optional[RecordType] = record


class DiscardMessageException(ErrorAfterSQSMessageReceived):
    """SQS message cannot be processed and should be discarded"""


class MalformedSQSMessageError(DiscardMessageException):
    pass


class MalformedS3ObjectError(DiscardMessageException):

    pass


class MissingS3ObjectError(DiscardMessageException):
    pass


class RetryReviewNotAllowed(ErrorAfterSQSMessageReceived):
    pass


class NoProfilesLoaded(DevCliException):
    pass
