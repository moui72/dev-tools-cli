from typing import TypedDict


class S3ObjectType(TypedDict):
    key: str
    size: str
    eTag: str
    versionId: str
    sequencer: str


class S3BucketType(TypedDict):
    name: str
    ownerIdentity: dict[str, str]
    arn: str


class S3Type(TypedDict):
    s3SchemaVersion: str
    configurationId: str
    bucket: S3BucketType
    object: S3ObjectType


class S3RecordType(TypedDict):
    eventVersion: str
    eventSource: str
    awsRegion: str
    eventTime: str
    eventName: str
    userIdentity: dict[str, str]
    requestParameters: dict[str, str]
    responseElements: dict[str, str]
    s3: S3Type


class S3MessageType(TypedDict):
    Records: list[S3RecordType]


class SQSRecordType(TypedDict):
    messageId: str
    receiptHandle: str
    body: str  # parses to S3MessageType
    attributes: dict[str, str]
    messageAttributes: dict[str, str]
    md5OfBody: str
    eventSource: str
    eventSourceARN: str
    awsRegion: str


class SQSMessageType(TypedDict):
    Records: list[SQSRecordType]


class NoteType(TypedDict):
    author: str
    subject: str
    body: str
    added: str


class ParamRequest(TypedDict):
    path: str
    encrypt: bool
    value: str
    notes: list[NoteType]
    requester: str
    reviewer: str
    requested_at: str
    reviewed_at: str
