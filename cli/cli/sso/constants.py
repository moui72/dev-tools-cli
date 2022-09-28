from enum import Enum


class OutputFormats(str, Enum):
    JSON = "json"
    YAML = "yaml"
    YAML_STREAM = "yaml-stream"
    TEXT = "text"
    TABLE = "table"
