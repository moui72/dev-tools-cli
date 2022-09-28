from datetime import timedelta
from enum import Enum
from pathlib import PosixPath
from typing import Union

AWS_SSO_ACCOUNT_ID_KEY = "sso_account_id"

AWS_SSO_ROLE_KEY = "sso_role_name"

BACKUP_SUFFIX = "dev-cli-backup-{timestamp}"

GOOGLE_TO_AZURE_CONFIG_UPDATE_MAP: dict[str, dict[str, Union[str, list[str]]]] = {
    "admin": {
        "GOOGLE_ROLE": "GGL-Administrators",
        "SHORT_NAME": "admin",
        "AZURE_ROLE": "Administrator",
        "PERMISSION_SETS": [
            "Prod-Administrator",
            "Stage-Administrator",
            "QA-Administrator",
        ],
    },
    "devprod": {
        "GOOGLE_ROLE": "GGL-DevelopersProd",
        "SHORT_NAME": "prod",
        "AZURE_ROLE": "DeveloperProd",
        "PERMISSION_SETS": [
            "Prod-DeveloperProd",
            "Stage-DeveloperProd",
            "QA-DeveloperProd",
        ],
    },
    "dev": {
        "GOOGLE_ROLE": "GGL-Developers",
        "SHORT_NAME": "dev",
        "AZURE_ROLE": "Developer",
        "PERMISSION_SETS": [
            "Prod-Developer",
            "Stage-Developer",
            "QA-Developer",
        ],
    },
    "devops": {
        "GOOGLE_ROLE": "GGL-DevOps",
        "SHORT_NAME": "devops",
        "AZURE_ROLE": "DevOps",
        "PERMISSION_SETS": [
            "Prod-DevOps",
            "Stage-DevOps",
            "QA-DevOps",
        ],
    },
    "sre": {
        "GOOGLE_ROLE": "GGL-SRE",
        "SHORT_NAME": "sre",
        "AZURE_ROLE": "SRE",
        "PERMISSION_SETS": [
            "Prod-SRE",
            "Stage-SRE",
            "QA-SRE",
        ],
    },
    "secops": {
        "GOOGLE_ROLE": "GGL-SecOps",
        "SHORT_NAME": "secops",
        "AZURE_ROLE": "SecOps",
        "PERMISSION_SETS": [
            "Prod-SecOps",
            "Stage-SecOps",
            "QA-SecOps",
        ],
    },
}
AWS_DIR_PATH = PosixPath("~").expanduser() / ".aws"
AWS_ACCESS_TOKEN_CACHE_DIR_PATH = AWS_DIR_PATH / "sso/cache"
AWS_CONFIG_FILE_PATH = AWS_DIR_PATH / "config"
AWS_CREDENTIAL_FILE_PATH = AWS_DIR_PATH / "credentials"
MAX_BACKUPS = 3
REFRESH_WHEN_TTL_BELOW_MINUTES = 5
MIN_TTL = timedelta(minutes=REFRESH_WHEN_TTL_BELOW_MINUTES)


class WriteableFiles(PosixPath, Enum):
    CONFIG = AWS_CONFIG_FILE_PATH
    CREDS = AWS_CREDENTIAL_FILE_PATH
