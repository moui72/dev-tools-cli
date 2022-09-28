import configparser
import json
from contextlib import nullcontext as does_not_raise
from datetime import datetime
from os import stat_result
from pathlib import PosixPath
from unittest.mock import MagicMock, mock_open

import pytest
from pytest_mock import MockerFixture

from cli.services.aws.config_service import AWS_CFG
from cli.services.aws.exceptions import ExpiredCredentials, NoCachedTokens


@pytest.mark.freeze_time("2022-08-24")
def test_AWS_CFG(mocker):
    dummy_config_data = {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
            "region": "us-east-2",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
            "region": "us-east-2",
        },
    }
    dummy_config = configparser.RawConfigParser(default_section="default")
    dummy_config.read_dict(dummy_config_data)
    AWS_CFG._reset()
    mocker.patch.object(AWS_CFG, "_config", dummy_config)

    assert AWS_CFG.front_matter == {
        "default": {"region": "us-east-2"},
        "dev": {"region": "us-east-2"},
    }
    assert AWS_CFG.profiles == {
        "profile dev": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678901",
            "sso_role_name": "Prod-Administrator",
            "region": "us-east-2",
        },
        "profile dev-qa": {
            "sso_start_url": "https://dev_tools.apps.com/start",
            "sso_region": "us-east-2",
            "output": "yaml",
            "sso_account_id": "12345678902",
            "sso_role_name": "QA-Administrator",
            "region": "us-east-2",
        },
    }

    assert AWS_CFG.get_profile_name_for_env("prod") == "profile dev"
    assert AWS_CFG.get_profile_name_for_env("stage") == "profile dev"
    assert AWS_CFG.get_profile_name_for_env("qa") == "profile dev-qa"


def get_mock_file_path(data, st_mtime=None):
    st_mtime = st_mtime or datetime.utcnow().timestamp()
    path = MagicMock(
        spec=PosixPath,
        open=mock_open(read_data=json.dumps(data)),
        stat=MagicMock(return_value=MagicMock(spec=stat_result, st_mtime=st_mtime)),
    )
    return path


all_tokens_expired = (
    {
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_1",
                "expiresAt": "2022-08-23T20:10:10Z",
            },
            st_mtime=1661203365.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_2",
                "expiresAt": "2022-08-22T20:10:10Z",
            },
            st_mtime=1661203375.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_3",
                "expiresAt": "2022-08-21T20:10:10Z",
            },
            st_mtime=1661203385.0,
        ),
    },
    pytest.raises(ExpiredCredentials),
    "EXPIRED",
)


no_tokens = (
    {
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "expiresAt": "2022-08-23T20:10:10Z",
            }
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "expiresAt": "2022-08-22T20:10:10Z",
            },
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "expiresAt": "2022-08-21T20:10:10Z",
            },
        ),
    },
    pytest.raises(NoCachedTokens),
    "NO CACHED TOKENS",
)


token_3_good = (
    {
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_1",
                "expiresAt": "2022-08-23T20:10:10Z",
            },
            st_mtime=1661203375.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_2",
                "expiresAt": "2022-08-22T20:10:10Z",
            },
            st_mtime=1661203385.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_3",
                "expiresAt": "2022-08-26T20:10:10Z",
            },
            st_mtime=1661203395.0,
        ),
    },
    does_not_raise(),
    "TOKEN_3",
)


token_2_good = (
    {
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_1",
                "expiresAt": "2022-08-23T20:10:10Z",
            },
            st_mtime=1661203375.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_2",
                "expiresAt": "2022-08-26T20:10:10Z",
            },
            st_mtime=1661203385.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_3",
                "expiresAt": "2022-08-21T20:10:10Z",
            },
            st_mtime=1661203395.0,
        ),
    },
    does_not_raise(),
    "TOKEN_2",
)


token_1_good = (
    {
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_1",
                "expiresAt": "2022-08-26T20:10:10Z",
            },
            st_mtime=1661203375.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_2",
                "expiresAt": "2022-08-22T20:10:10Z",
            },
            st_mtime=1661203385.0,
        ),
        get_mock_file_path(
            {
                "startUrl": "https://dev_tools.apps.com/start",
                "region": "us-east-2",
                "accessToken": "TOKEN_3",
                "expiresAt": "2022-08-21T20:10:10Z",
            },
            st_mtime=1661203395.0,
        ),
    },
    does_not_raise(),
    "TOKEN_1",
)


@pytest.mark.freeze_time("2022-08-24")
@pytest.mark.parametrize(
    "mock_sso_cache,expected_to_raise,expected_result",
    [all_tokens_expired, no_tokens, token_1_good, token_2_good, token_3_good],
)
def test_get_latest_token(
    mocker: MockerFixture,
    mock_sso_cache,
    expected_to_raise,
    expected_result,
):
    mocker.patch(
        "cli.services.aws.config_service.AWSConfigService._sso_cache",
        return_value=mock_sso_cache,
    )
    with expected_to_raise:
        assert AWS_CFG.get_latest_token() == expected_result
