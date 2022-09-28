import configparser
from collections import defaultdict
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from cli.main import app
from cli.services.aws.config_service import WriteableFiles
from cli.sso.utils import AWS_CFG
from cli.types import SimpleNestedDict


def config_from_dict(dict: dict):
    dummy_config = configparser.RawConfigParser(default_section="default")
    dummy_config.clear()
    dummy_config.read_dict(dict)
    return dummy_config


def config_to_dict(config: configparser.RawConfigParser):
    return {
        section_name: {k: str(v) for k, v in section.items()}
        for section_name, section in config.items()
    }


SSO_CMD = ["sso"]
LOGIN_CMD = SSO_CMD + ["login"]
CONFIG_CMD = SSO_CMD + ["config"]
UPDATE_CMD = CONFIG_CMD + ["update"]
ADD_PROFILES_CMD = CONFIG_CMD + ["add-profiles"]
NEW_CMD = CONFIG_CMD + ["new"]
MAKE_PRIMARY_CMD = CONFIG_CMD + ["make-primary"]


TEST_CONFIGS: dict[str, SimpleNestedDict] = {
    "EMPTY": {},
    "NEW": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Developer",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Developer",
        },
        "profile dev-stage": {
            "output": "yaml",
            "region": "us-east-2",
            "sso_account_id": "12345678901",
            "sso_region": "us-east-2",
            "sso_role_name": "Stage-Developer",
            "sso_start_url": "https://dev_tools.apps.com/start",
        },
    },
    "BASIC_ADMIN": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
        },
    },
    "MULTIPLE_ROLES": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
        },
        "profile dev-dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "Prod-Developer",
        },
        "profile dev-qa-dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Developer",
        },
    },
    "UPDATED": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "region": "us-east-2",
            "sso_region": "us-east-2",
            "google_config.ask_role": "False",
            "google_config.keyring": "False",
            "google_config.duration": "3600",
            "google_config.google_idp_id": "C027up00p",
            "google_config.role_arn": "arn:aws:iam::12345678901:role/GGL-Administrators",
            "google_config.google_sp_id": "485268859941",
            "google_config.u2f_disabled": "False",
            "google_config.google_username": "someone@testing.com",
            "sso_start_url": "https://dev_tools.apps.com/start",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
        },
        "profile dev-qa": {
            "region": "us-east-2",
            "sso_region": "us-east-2",
            "google_config.ask_role": "False",
            "google_config.keyring": "False",
            "google_config.duration": "3600",
            "google_config.google_idp_id": "C027up00p",
            "google_config.role_arn": "arn:aws:iam::12345678902:role/GGL-Administrators",
            "google_config.google_sp_id": "485268859941",
            "google_config.u2f_disabled": "False",
            "google_config.google_username": "someone@testing.com",
            "sso_start_url": "https://dev_tools.apps.com/start",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
        },
        "profile dev-stage-admin": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Stage-Administrator",
        },
    },
    "GOOGLE": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "region": "us-east-2",
            "google_config.ask_role": "False",
            "google_config.keyring": "False",
            "google_config.duration": "3600",
            "google_config.google_idp_id": "C027up00p",
            "google_config.role_arn": "arn:aws:iam::12345678901:role/GGL-Administrators",
            "google_config.google_sp_id": "485268859941",
            "google_config.u2f_disabled": "False",
            "google_config.google_username": "someone@testing.com",
        },
        "profile dev-qa": {
            "region": "us-east-2",
            "google_config.ask_role": "False",
            "google_config.keyring": "False",
            "google_config.duration": "3600",
            "google_config.google_idp_id": "C027up00p",
            "google_config.role_arn": "arn:aws:iam::12345678902:role/GGL-Administrators",
            "google_config.google_sp_id": "485268859941",
            "google_config.u2f_disabled": "False",
            "google_config.google_username": "someone@testing.com",
        },
    },
    "QA-Developer": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Developer",
        },
    },
    "all-Developer": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Developer",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Developer",
        },
        "profile dev-stage": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Stage-Developer",
        },
    },
    "Prod-Administrator": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
        },
    },
    "Stage-Administrator QA-Administrator": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev-stage": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Stage-Administrator",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
        },
    },
    "Prod-SRE": {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-SRE",
        },
    },
    "GGL-SRE-v2": {},
    "QA-DevOps GGL-SRE-v2": {},
}

EXPECTED_CREDENTIALS = {
    name: {
        profile_name.split(" ")[-1]: {
            "aws_access_key_id": "accessKeyId",
            "aws_secret_access_key": "secretAccessKey",
            "aws_session_token": "sessionToken",
            "aws_session_expiration": "expiration",
        }
        for profile_name in profile
        if profile_name.startswith("profile ")
    }
    for name, profile in TEST_CONFIGS.items()
}
EXPECTED_EXIT_CODE = defaultdict(lambda: 0)
EXPECTED_EXIT_CODE["EMPTY"] = 1


@pytest.mark.freeze_time("2022-08-24")
@pytest.mark.parametrize(
    "name,mock_config_object",
    [(name, config) for name, config in TEST_CONFIGS.items() if name.isupper()],
)
def test_login(mocker: MockerFixture, name: str, mock_config_object: dict):
    mocker.patch(
        "cli.sso.utils.get_role_credentials",
        lambda profile, token, profile_name: (
            profile_name.split(" ")[-1],
            {
                "aws_access_key_id": "accessKeyId",
                "aws_secret_access_key": "secretAccessKey",
                "aws_session_token": "sessionToken",
                "aws_session_expiration": "expiration",
            },
        ),
    )
    mocker.patch.object(AWS_CFG, "get_latest_token")
    mocker.patch("cli.sso.utils.authenticate", return_value=0)
    AWS_CFG._reset()
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict(mock_config_object),
    )
    mock_writer = mocker.patch.object(AWS_CFG, "write_sections_to_file")
    runner = CliRunner()
    result = runner.invoke(app, LOGIN_CMD)
    mock_writer.assert_called_once_with(
        sections=EXPECTED_CREDENTIALS[name], file=WriteableFiles.CREDS, overwrite=True
    )
    assert result.exit_code == EXPECTED_EXIT_CODE[name]


def test_config_update(mocker: MockerFixture):
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict(TEST_CONFIGS["GOOGLE"]),
    )
    mock_writer = mocker.patch.object(AWS_CFG, "write_sections_to_file")
    runner = CliRunner()
    result = runner.invoke(app, UPDATE_CMD)
    mock_writer.assert_called_once_with(
        sections=TEST_CONFIGS["UPDATED"], file=WriteableFiles.CONFIG
    )
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "profiles_to_add",
    [
        ["QA-Developer"],
        ["all-Developer"],
        ["Prod-Administrator"],
        ["Stage-Administrator", "QA-Administrator"],
        ["Prod-SRE"],
    ],
)
def test_config_add_profiles__empty_base__happy_path(mocker, profiles_to_add):
    AWS_CFG._reset()
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict({}),
    )
    mock_writer = mocker.patch.object(AWS_CFG, "write_sections_to_file")
    runner = CliRunner()
    result = runner.invoke(app, ADD_PROFILES_CMD + profiles_to_add)
    mock_writer.assert_called_once_with(
        sections=TEST_CONFIGS[" ".join(profiles_to_add)],
        file=WriteableFiles.CONFIG,
    )
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "profiles_to_add",
    [
        ["GGL-SRE-v2"],
        ["QA-DevOps", "GGL-SRE-v2"],
    ],
)
def test_config_add_profiles__empty_base__error(mocker, profiles_to_add):
    AWS_CFG._reset()
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict({}),
    )
    mock_writer = mocker.patch.object(AWS_CFG, "write_sections_to_file")
    runner = CliRunner()
    result = runner.invoke(app, ADD_PROFILES_CMD + profiles_to_add)
    mock_writer.assert_not_called()
    assert result.exit_code > 0


def test_new__success(mocker: MockerFixture):
    MockWriteableFiles = mocker.patch(
        "cli.sso.manage_config.WriteableFiles",
        MagicMock(**{"CONFIG.value.exists": MagicMock(return_value=False)}),
    )
    mock_writer = mocker.spy(AWS_CFG, "write_sections_to_file")
    runner = CliRunner()
    result = runner.invoke(app, NEW_CMD)
    mock_writer.assert_called_once_with(
        sections=TEST_CONFIGS["NEW"],
        file=MockWriteableFiles.CONFIG,
        overwrite=False,
    )
    MockWriteableFiles.CONFIG.value.open.assert_called_once()
    assert result.exit_code == 0


def test_new__fail(mocker: MockerFixture):
    mock_writer = mocker.spy(AWS_CFG, "write_sections_to_file")
    MockWriteableFiles = mocker.patch(
        "cli.sso.manage_config.WriteableFiles",
        MagicMock(**{"CONFIG.value.exists": MagicMock(return_value=True)}),
    )

    AWS_CFG._reset()
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict(TEST_CONFIGS["BASIC_ADMIN"]),
    )
    runner = CliRunner()
    result = runner.invoke(app, NEW_CMD)
    mock_writer.assert_called_once_with(
        sections=TEST_CONFIGS["NEW"],
        file=MockWriteableFiles.CONFIG,
        overwrite=False,
    )
    MockWriteableFiles.CONFIG.value.open.assert_not_called()
    assert result.exit_code > 0


@pytest.mark.parametrize("flag", [["--destroy-existing"], ["-f"]])
def test_new__overwrite_success(mocker, flag):
    mock_writer = mocker.spy(AWS_CFG, "write_sections_to_file")
    MockWriteableFiles = mocker.patch(
        "cli.sso.manage_config.WriteableFiles",
        MagicMock(**{"CONFIG.value.exists": MagicMock(return_value=True)}),
    )
    AWS_CFG._reset()
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict(TEST_CONFIGS["BASIC_ADMIN"]),
    )
    runner = CliRunner()
    result = runner.invoke(app, NEW_CMD + flag)
    mock_writer.assert_called_once_with(
        sections=TEST_CONFIGS["NEW"],
        file=MockWriteableFiles.CONFIG,
        overwrite=True,
    )
    MockWriteableFiles.CONFIG.value.open.assert_called_once()
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "profile_name,expected_sections",
    [
        (
            ["dev"],
            None,
        ),
        (
            ["dev-dev"],
            {
                "default": {"region": "us-east-2"},
                "dev": {"region": "us-east-2"},
                "profile dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "Prod-Developer",
                },
                "profile dev-qa": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Administrator",
                },
                "profile dev-qa-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Developer",
                },
                "profile dev-admin": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678901",
                    "sso_role_name": "Prod-Administrator",
                },
            },
        ),
        (
            ["dev-admin"],
            {
                "default": {"region": "us-east-2"},
                "dev": {"region": "us-east-2"},
                "profile dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678901",
                    "sso_role_name": "Prod-Administrator",
                },
                "profile dev-qa": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Administrator",
                },
                "profile dev-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "Prod-Developer",
                },
                "profile dev-qa-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Developer",
                },
            },
        ),
        (
            ["dev-all-admin"],
            {
                "default": {"region": "us-east-2"},
                "dev": {"region": "us-east-2"},
                "profile dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678901",
                    "sso_role_name": "Prod-Administrator",
                },
                "profile dev-qa": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Administrator",
                },
                "profile dev-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "Prod-Developer",
                },
                "profile dev-qa-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Developer",
                },
            },
        ),
        (
            ["dev-qa"],
            {
                "default": {"region": "us-east-2"},
                "dev": {"region": "us-east-2"},
                "profile dev-admin": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678901",
                    "sso_role_name": "Prod-Administrator",
                },
                "profile dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Administrator",
                },
                "profile dev-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "Prod-Developer",
                },
                "profile dev-qa-dev": {
                    "sso_start_url": "https://dev_tools.apps.com/start",
                    "sso_region": "us-east-2",
                    "region": "us-east-2",
                    "output": "yaml",
                    "sso_account_id": "12345678902",
                    "sso_role_name": "QA-Developer",
                },
            },
        ),
    ],
)
def test_make_primary__success(mocker, profile_name, expected_sections):
    mock_writer = mocker.patch.object(AWS_CFG, "write_sections_to_file")
    mocker.patch.object(
        AWS_CFG,
        "_config",
        config_from_dict(TEST_CONFIGS["MULTIPLE_ROLES"]),
    )
    runner = CliRunner()
    result = runner.invoke(app, MAKE_PRIMARY_CMD + profile_name)
    if expected_sections:
        mock_writer.assert_called_once_with(
            sections=expected_sections,
            file=WriteableFiles.CONFIG,
        )
    else:
        mock_writer.assert_not_called()
    assert result.exit_code == 0
