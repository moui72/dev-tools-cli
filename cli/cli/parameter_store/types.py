from enum import Enum
from typing import Optional, TypedDict

from pydantic import create_model_from_typeddict

isoformat_str = r"^\d{4}-\d{2}-\d{2}T\d{2}(:\d{2}){1,3}$"


class ObjectType(TypedDict):
    key: str
    size: str
    eTag: str
    versionId: str
    sequencer: str


class BucketType(TypedDict):
    name: str
    ownerIdentity: dict[str, str]
    arn: str


class S3Type(TypedDict):
    s3SchemaVersion: str
    configurationId: str
    bucket: BucketType
    object: ObjectType


class RecordType(TypedDict):
    s3: S3Type
    userIdentity: str


class MessageType(TypedDict):
    Records: list[RecordType]


class NoteType(TypedDict):
    author: Optional[str]
    subject: Optional[str]
    body: str
    added: str


class RequestType(TypedDict):
    path: str
    encrypt: bool
    value: str
    notes: list[NoteType]
    requester: str
    reviewer: Optional[str]
    requested_at: str
    reviewed_at: Optional[str]
    touches: int
    id: str


BucketModel = create_model_from_typeddict(BucketType)
MessageModel = create_model_from_typeddict(MessageType)
NoteModel = create_model_from_typeddict(NoteType)
ObjectModel = create_model_from_typeddict(ObjectType)
RecordModel = create_model_from_typeddict(RecordType)
S3Model = create_model_from_typeddict(S3Type)
S3ObjectBodyModel = create_model_from_typeddict(RequestType)


class EnvDisplay(str, Enum):
    QA = "QA"
    PROD = "Prod"
    STAGE = "Stage"

    @classmethod
    def _missing_(cls, value):
        """Allows case insensitive member matching"""
        for member in cls:
            if member.value.upper() == value.upper():
                return member


class DecisionResponse(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"

    @classmethod
    def _missing_(cls, value):
        """Allows case insensitive first-letter member matching"""
        for member in cls:
            if (
                member.value == value.upper()
                or member.value[0].upper() == value.upper()
            ):
                return member
