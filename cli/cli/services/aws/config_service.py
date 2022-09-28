import json
import logging
from collections import defaultdict
from configparser import RawConfigParser
from datetime import datetime, timezone
from pathlib import PosixPath
from typing import Optional

from dateutil.parser import isoparse

from cli.constants import (
    AWS_GOOGLE_ROLE_KEY,
    ENV_TO_AWS_ACCOUNT,
    PRIORITY_BY_ROLE,
    STAGE_ON_PROD_ACCOUNT,
)
from cli.services.aws.constants import (
    AWS_ACCESS_TOKEN_CACHE_DIR_PATH,
    AWS_CONFIG_FILE_PATH,
    AWS_SSO_ACCOUNT_ID_KEY,
    AWS_SSO_ROLE_KEY,
    BACKUP_SUFFIX,
    MAX_BACKUPS,
    MIN_TTL,
    WriteableFiles,
)
from cli.services.aws.exceptions import (
    ExpiredCredentials,
    InvalidProfile,
    NoCachedTokens,
    NoValidProfileError,
)
from cli.types import SimpleNestedDict


def load_config_from_file(file=AWS_CONFIG_FILE_PATH):
    config = RawConfigParser()
    config.clear()
    config.read(AWS_CONFIG_FILE_PATH)
    return config


def get_ttl(expiry):
    return expiry - datetime.now(tz=timezone.utc)


class AWSConfigService:
    _config: Optional[RawConfigParser] = None
    _front: dict[int, SimpleNestedDict] = {}
    _profiles: dict[int, SimpleNestedDict] = {}

    def _reset(self):
        self._config = None
        self._front: dict[int, SimpleNestedDict] = {}
        self._profiles: dict[int, SimpleNestedDict] = {}

    @property
    def _aws_config(self):
        if not self._config:
            self._config = load_config_from_file()
        return self._config

    @property
    def _aws_config_hash(self):
        items = {
            f"{profile_name}:{k}:{v}"
            for profile_name, profile in self._aws_config.items()
            for k, v in profile.items()
        }
        return hash(frozenset(items))

    @property
    def front_matter(self):
        key = self._aws_config_hash
        if key not in self._front:
            self._front[key] = {
                section: {k: v for k, v in self._aws_config[section].items()}
                for section in self._aws_config
                if not section.lower().startswith("profile")
                and not section == "DEFAULT"
            }
        return self._front[key]

    @property
    def profiles(self):
        key = self._aws_config_hash
        if key not in self._profiles:
            self._profiles[key] = {
                section: {k: v for k, v in self._aws_config[section].items()}
                for section in self._aws_config
                if section.lower().startswith("profile")
            }
        return self._profiles[key]

    @staticmethod
    def _sso_cache():
        return set(AWS_ACCESS_TOKEN_CACHE_DIR_PATH.glob("*.json"))

    @staticmethod
    def backup_file(file: PosixPath):
        backup_path = file.with_suffix(
            BACKUP_SUFFIX.format(timestamp=str(int(datetime.utcnow().timestamp())))
        )
        file.rename(backup_path)
        logging.info(
            f"Saved backup: {file.parent}/{{{file.name} -> {backup_path.name}}}"
        )

    @staticmethod
    def cleanup_older_backups(file: PosixPath):
        backups = file.parent.glob(BACKUP_SUFFIX.format(timestamp="*"))
        by_mtime = {f.stat().st_mtime: f for f in backups}
        mtimes = sorted(by_mtime.keys())
        to_delete = max(len(mtimes) - MAX_BACKUPS, 0)
        for i in range(to_delete):
            mtime = mtimes[i]
            by_mtime[mtime].unlink()
        print(f"Removed {to_delete} older backups of {file}")

    @staticmethod
    def write_sections_to_file(
        sections: SimpleNestedDict,
        file: WriteableFiles,
        overwrite=False,
    ):
        _file = file.value
        if _file.exists():
            if not overwrite:
                raise FileExistsError()
            else:
                AWSConfigService.backup_file(_file)

        total_bytes_written = 0
        front = []
        profiles = []
        for name in sections:
            if name.startswith("profile"):
                profiles.append(name)
            else:
                front.append(name)
        front = sorted(front)
        profiles = sorted(profiles)
        sections_sorted = front + profiles
        with _file.open(mode="w+") as f:
            for name in sections_sorted:
                section = sections[name]
                total_bytes_written += f.write(f"[{name}]\n")
                for key, value in section.items():
                    f.write(f"{key} = {value}\n")
                total_bytes_written += f.write("\n")
        return total_bytes_written

    @classmethod
    def get_latest_token(cls, files: set[PosixPath] = None) -> str:
        if files is None:
            _files: set[PosixPath] = cls._sso_cache()
        else:
            _files = files
        newest_ts = 0.0
        newest_file_path: Optional[PosixPath] = None
        for file in _files:
            if file.stat().st_mtime > newest_ts:
                newest_ts = file.stat().st_mtime
                newest_file_path = file
        if not newest_file_path:
            raise NoCachedTokens(
                "No valid tokens were found. Please run dev sso login."
            )
        with newest_file_path.open() as f:
            token_data = json.load(f)
        if "accessToken" not in token_data:
            logging.debug(
                f"File does not contain accessToken, getting next newest file ({newest_file_path})"
            )
            _files.remove(newest_file_path)
            return cls.get_latest_token(files=_files)
        expiry = isoparse(token_data["expiresAt"])
        ttl = get_ttl(expiry)
        logging.debug(f"Token TTL: {ttl}")
        if ttl < MIN_TTL:
            if len(list(_files)) <= 1:
                message = (
                    f"Token expired or expiring soon ({expiry.isoformat(timespec='minutes')}). Please login again with"
                    + " `dev sso login`"
                )
                raise ExpiredCredentials(message, expires=expiry)
            else:
                _files.remove(newest_file_path)
                return cls.get_latest_token(files=_files)
        return token_data["accessToken"]

    @staticmethod
    def _profile_matches_account(profile: SimpleNestedDict, account_id):
        profile_matches_sso: bool = (
            AWS_SSO_ACCOUNT_ID_KEY in profile
            and account_id == profile[AWS_SSO_ACCOUNT_ID_KEY]
        )
        profile_matches_google = account_id in profile.get(AWS_GOOGLE_ROLE_KEY, {})
        return profile_matches_sso or profile_matches_google

    @staticmethod
    def _priority_of_profile(profile):
        if AWS_SSO_ROLE_KEY in profile:
            splitter = "-"
            key = AWS_SSO_ROLE_KEY
        elif AWS_GOOGLE_ROLE_KEY in profile:
            splitter = "role/"
            key = AWS_GOOGLE_ROLE_KEY
        else:
            raise InvalidProfile()
        role = profile[key].split(splitter)[-1]
        return PRIORITY_BY_ROLE[role]

    def get_profile_name_for_env(self, env: str, skip_priorities: set[int] = None):
        skip_priorities = skip_priorities or set()
        env = env.lower()
        if STAGE_ON_PROD_ACCOUNT:
            if env == "stage":
                env = "prod"
        account_id = ENV_TO_AWS_ACCOUNT[env]
        profiles_for_account = defaultdict(list)
        for profile_name, profile in self.profiles.items():
            if self._profile_matches_account(profile=profile, account_id=account_id):
                profiles_for_account[self._priority_of_profile(profile)].append(
                    profile_name
                )
        for priorty in sorted(profiles_for_account.keys()):
            if priorty not in skip_priorities and priorty in profiles_for_account:
                return profiles_for_account[priorty][0]
        raise NoValidProfileError(
            f"Could not find any valid profiles for {env} in your config."
            + " You could generate a new config, see `dev sso config new --help`"
        )

    def as_dict(self):
        return {
            section: {k: v for k, v in self._aws_config[section].items()}
            for section in self._aws_config
        }


AWS_CFG = AWSConfigService()
