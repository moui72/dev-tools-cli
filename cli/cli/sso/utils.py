import logging
from random import choice
from subprocess import run
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from cli.constants import (
    ALL_CORE_ENVS,
    AWS_ACCOUNT_TO_ENV,
    AWS_GOOGLE_ROLE_KEY,
    AWS_SSO_REGION_KEY,
    DEFAULT_PROFILE_BASE,
    ENV_TO_AWS_ACCOUNT,
)
from cli.services.aws.config_service import AWS_CFG
from cli.services.aws.constants import (
    AWS_SSO_ACCOUNT_ID_KEY,
    AWS_SSO_ROLE_KEY,
    GOOGLE_TO_AZURE_CONFIG_UPDATE_MAP,
    WriteableFiles,
)
from cli.services.aws.exceptions import InvalidProfile, NeedAuth, NoSuchProfile
from cli.sso.constants import OutputFormats
from cli.sso.exceptions import BadEnvInRole
from cli.sso.words import WORDS
from cli.types import SimpleNestedDict


def authenticate():
    code: Optional[int] = None
    while code != 0:
        try:
            proc = run(["aws", "sso", "login"])
            code = proc.returncode
            if code == 0:
                break
        except Exception as e:
            logging.error("Error running `aws sso login` as subprocess")
            logging.error(e)
        if input("Try again? (defaults to yes; enter 'no' to exit) ").lower() == "no":
            break
    return code


def get_role_credentials(profile: SimpleNestedDict, token: str, profile_name: str):
    client = boto3.client("sso", region_name=profile[AWS_SSO_REGION_KEY])
    r = client.get_role_credentials(
        roleName=profile[AWS_SSO_ROLE_KEY],
        accountId=profile[AWS_SSO_ACCOUNT_ID_KEY],
        accessToken=token,
    )
    _prefix, _separator, credential_name = profile_name.rpartition(" ")

    return credential_name, {
        "aws_access_key_id": r["roleCredentials"]["accessKeyId"],
        "aws_secret_access_key": r["roleCredentials"]["secretAccessKey"],
        "aws_session_token": r["roleCredentials"]["sessionToken"],
        "aws_session_expiration": r["roleCredentials"]["expiration"],
    }


def generate_credentials_file() -> tuple[int, dict[str, str], dict[str, Exception]]:
    try:
        token = AWS_CFG.get_latest_token()
    except NeedAuth:
        logging.warning("AWS SSO login needed")
        code = authenticate()
        if code != 0:
            logging.error("AWS SSO login failed. Exiting")
            return exit()
        else:
            return generate_credentials_file()
    profiles = AWS_CFG.profiles
    credentials = {}
    errors: dict[str, Exception] = {}
    for profile_name, profile_data in profiles.items():
        try:
            credential_name, credential = get_role_credentials(
                profile=profile_data, token=token, profile_name=profile_name
            )
            credentials[credential_name] = credential
        except ClientError as exc:
            errors[profile_name] = exc
    return (
        AWS_CFG.write_sections_to_file(
            sections=credentials, file=WriteableFiles.CREDS, overwrite=True
        ),
        credentials,
        errors,
    )


def make_profile(role: str, existing: dict[str, str]):
    env, _ = role.split("-")
    new_fields = {
        AWS_SSO_ACCOUNT_ID_KEY: ENV_TO_AWS_ACCOUNT[env.lower()],
        AWS_SSO_ROLE_KEY: role,
    }
    existing.update(new_fields)
    return existing


def is_aws_sso_compatible_profile(profile):
    return AWS_SSO_ROLE_KEY in profile


def is_aws_google_auth_compatible_profile(profile):
    return AWS_GOOGLE_ROLE_KEY in profile


def new_profile_from_base(output: OutputFormats = OutputFormats.YAML):
    new_profile = DEFAULT_PROFILE_BASE.copy()
    new_profile["output"] = output.value
    return new_profile


def expand_envs_from_role(role):
    env, role = role.split("-")
    if env == "all":
        envs = ALL_CORE_ENVS
    else:
        if env not in ALL_CORE_ENVS:
            raise BadEnvInRole()
        envs = [env]
    return envs, role


def get_arbitrary_suffix(name):
    suffix = choice(list(WORDS))
    if suffix in name:
        return get_arbitrary_suffix(name)
    return suffix


def specify_profile_name(previous_name, profiles):
    profile = profiles[previous_name]
    if AWS_SSO_ROLE_KEY in profile:
        env, role = profile[AWS_SSO_ROLE_KEY].split("-")
        nickname = find_shortname(role, key="AZURE_ROLE")
    elif AWS_GOOGLE_ROLE_KEY in profile:
        role_parts = profile[AWS_GOOGLE_ROLE_KEY].split(":")
        account_id = role_parts[-2]
        role = role_parts[-1][5:]
        env = AWS_ACCOUNT_TO_ENV[account_id][0]
        nickname = find_shortname(profile[AWS_GOOGLE_ROLE_KEY])
    else:
        raise InvalidProfile(f"{profile}")
    print(f"env: {env}, role: {role}, nickname: {nickname}")
    new_profile_name = "dev"
    if env.lower() != "prod":
        new_profile_name += f"-{env.lower()}"
    if f"profile {new_profile_name}" in profiles:
        print(
            f"clash, add nickname \n> {previous_name} -> {new_profile_name}\n{profiles.keys()}"
        )
        new_profile_name += f"-{nickname}"
    while f"profile {new_profile_name}" in profiles:
        print(
            f"clash, add suffix \n> {previous_name} -> {new_profile_name}\n{profiles.keys()}"
        )
        suffix = get_arbitrary_suffix(new_profile_name)
        new_profile_name += f"-{suffix}"
    return new_profile_name


def find_shortname(value: str, key="GOOGLE_ROLE"):
    if key == "AZURE_ROLE":
        for prefix in ["QA-", "Stage-", "Prod-"]:
            value = value.removeprefix(prefix)
    for short_name, info in GOOGLE_TO_AZURE_CONFIG_UPDATE_MAP.items():
        if info[key] == value:
            return short_name


def find_info(value, key="GOOGLE_ROLE"):
    for info in GOOGLE_TO_AZURE_CONFIG_UPDATE_MAP.values():
        if info[key] == value:
            return info


def rename(target: str, source: str, existing_profiles: SimpleNestedDict):
    target_name = f"profile {target}"
    source_name = f"profile {source}"
    if source_name not in existing_profiles:
        raise NoSuchProfile(f"{source_name.capitalize()} does not exist")
    if (
        target_name in existing_profiles
        and existing_profiles[target_name][AWS_SSO_ROLE_KEY]
        != existing_profiles[source_name][AWS_SSO_ROLE_KEY]
    ):
        profile_to_rename = existing_profiles[target_name]
        new_name_for_existing_profile = specify_profile_name(
            target_name,
            profiles=existing_profiles,
        )
        print(f"Renaming existing {target} to {new_name_for_existing_profile}")
        existing_profiles[
            f"profile {new_name_for_existing_profile}"
        ] = profile_to_rename
    existing_profiles[target_name] = existing_profiles[source_name]
    del existing_profiles[source_name]
