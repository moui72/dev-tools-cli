from enum import Enum

from rich.theme import Theme

AWS_DEFAULT_REGION = "us-east-2"
AWS_SSO_START_URL = "https://dev_tools.apps.com/start"
AWS_SSO_REGION_KEY = "sso_region"


DEFAULT_ROLE = "all-Developer"
DEFAULT_ROLES = [DEFAULT_ROLE]
DEFAULT_PROFILE_BASE = {
    "sso_start_url": AWS_SSO_START_URL,
    AWS_SSO_REGION_KEY: AWS_DEFAULT_REGION,
    "region": AWS_DEFAULT_REGION,
    "output": "yaml",
}
ALL_CORE_ENVS = [
    "Prod",
    "Stage",
    "QA",
]

AWS_ACCOUNT_TO_ENV = {
    "012345678901": [
        "prod",
    ],
    "012345678902": ["qa", "dev"],
    "012345678903": ["stage"],
    "012345678904": ["management"],
}

ENV_TO_AWS_ACCOUNT = {
    env: account for account, envs in AWS_ACCOUNT_TO_ENV.items() for env in envs
}

AWS_GOOGLE_ROLE_KEY = "google_config.role_arn"
AWS_GOOGLE_CONFIG_USER_KEY = "google_config.google_username"
AWS_GOOGLE_CONFIG_ROLE_SEPARATOR = ":"
AWS_GOOGLE_CONFIG_ROLE_PREFIX = "role/"

ENVIRONMENTS = list(ENV_TO_AWS_ACCOUNT.keys())

ROLE_PRIORITY = [
    ["Administrator"],
    ["SRE", "DevOps"],
    ["DeveloperProd"],
    ["Developer"],
    ["Analyst"],
]
PRIORITY_BY_ROLE = {role: i for i, roles in enumerate(ROLE_PRIORITY) for role in roles}


class CaseInsenstiveEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        return cls(value.lower())


class CoreEnv(CaseInsenstiveEnum):
    QA = "qa"
    STAGE = "stage"
    PROD = "prod"
    ALL = "all"


class ReviewableEnv(CaseInsenstiveEnum):
    DEV = "dev"
    QA = "qa"
    STAGE = "stage"
    PROD = "prod"


GLOBAL_RICH_CONSOLE_THEME = Theme({"subtle": "grey58"})
