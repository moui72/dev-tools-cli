import argparse
from enum import IntEnum

import toml

RC_TAG = "-rc"
TOML_FILE_PATH = "pyproject.toml"


class VersionIncrement(IntEnum):
    major = 0
    current = 1
    minor = 1
    patch = 2

    def __str__(self):
        return self.name


def increment_version(version: str, increment: VersionIncrement) -> str:
    """
    Helper function to increment the version.
    """
    version_to_release_split = version.split(".")
    version_to_release_split[increment.value] = str(
        int(version_to_release_split[increment.value]) + 1
    )
    for i in range(increment + 1, len(version_to_release_split)):
        version_to_release_split[i] = "0"
    return ".".join(version_to_release_split)


def cut_release(version_increment: VersionIncrement):
    """
    Cuts the release by updating the notifier version based on the update,
    then removing the -rc tag to prepare the notifier for release.
    """
    with open(TOML_FILE_PATH, "r") as f:
        toml_dict = toml.loads(f.read())
        current_version = toml_dict["versions"]["current_version"]
        stable_version = toml_dict["versions"]["stable_version"]

    if version_increment == VersionIncrement.current:
        version_to_release = current_version
    else:
        version_to_release = increment_version(stable_version, version_increment)

    version_to_release = version_to_release.replace(RC_TAG, "")

    with open(TOML_FILE_PATH, "w") as f:
        toml_dict["tool"]["poetry"]["version"] = version_to_release
        toml_dict["versions"]["current_version"] = version_to_release
        f.write(toml.dumps(toml_dict))

    print(version_to_release)


def prepare_next_release():
    """
    Prepares for the next release by setting the new stable and next "anticipated" release.
    Next release is assumed to be a minor release, then tagged with an -rc suffix.
    """
    with open(TOML_FILE_PATH, "r") as f:
        toml_dict = toml.loads(f.read())
        released_version = toml_dict["versions"]["current_version"].replace(RC_TAG, "")

    with open(TOML_FILE_PATH, "w") as f:
        toml_dict["versions"]["stable_version"] = released_version
        next_version = (
            increment_version(released_version, VersionIncrement.minor) + RC_TAG
        )
        toml_dict["tool"]["poetry"]["version"] = next_version
        toml_dict["versions"]["current_version"] = next_version
        f.write(toml.dumps(toml_dict))


def get_release_verison():
    with open(TOML_FILE_PATH, "r") as f:
        toml_dict = toml.loads(f.read())
        released_version = toml_dict["tool"]["poetry"]["version"]
        # Don't remove print statement, as this is used in the GitHub CI to save the version.
        print(released_version)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        type=str,
        choices=["cut-release", "prepare-next-release", "get-release-version"],
    )
    parser.add_argument(
        "--increment",
        dest="version_increment",
        choices=VersionIncrement,
        type=VersionIncrement.__getitem__,
        default=VersionIncrement.current.name,
    )
    args = parser.parse_args()

    cmd = args.command
    version_increment = args.version_increment

    if cmd == "cut-release":
        cut_release(version_increment)
    elif cmd == "get-release-version":
        get_release_verison()
    elif cmd == "prepare-next-release":
        prepare_next_release()
    else:
        print(f"Command {cmd} not implemented.")


if __name__ == "__main__":
    main()
