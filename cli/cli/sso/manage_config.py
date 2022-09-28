import typer
from rich import print

from cli.constants import (
    ALL_CORE_ENVS,
    AWS_ACCOUNT_TO_ENV,
    AWS_DEFAULT_REGION,
    AWS_GOOGLE_CONFIG_ROLE_PREFIX,
    AWS_GOOGLE_CONFIG_ROLE_SEPARATOR,
    DEFAULT_ROLE,
    CoreEnv,
)
from cli.services.aws.config_service import (
    AWS_CFG,
    AWS_GOOGLE_ROLE_KEY,
    AWS_SSO_ROLE_KEY,
    BACKUP_SUFFIX,
    WriteableFiles,
)
from cli.services.aws.exceptions import NoSuchProfile
from cli.sso.constants import OutputFormats
from cli.sso.exceptions import BadEnvInRole
from cli.sso.utils import (
    expand_envs_from_role,
    find_info,
    find_shortname,
    get_arbitrary_suffix,
    make_profile,
    new_profile_from_base,
    rename,
)
from cli.types import SimpleNestedDict

app = typer.Typer()


@app.command()
def update(output_format: OutputFormats = OutputFormats.YAML.value):  # type: ignore[assignment]
    """Automatically migrates your aws-google-login aws config file for use with the new Azure-AWS SSO paradigm, while
    maintaining compatibility with aws-google-login
    """
    existing_profiles = AWS_CFG.profiles
    new_config: SimpleNestedDict = AWS_CFG.front_matter.copy()
    new_profile = new_profile_from_base(output=output_format)
    covered_roles: set[str] = set()
    updated: set[str] = set()
    created: set[str] = set()
    for name, profile in existing_profiles.items():
        if AWS_GOOGLE_ROLE_KEY not in profile:
            print(
                f"[grey66 italic]Leaving {name} unchanged as it is not an aws-google-auth profile[/]"
            )
            new_config[name] = profile

            continue
        google_raw_role_string = profile[AWS_GOOGLE_ROLE_KEY]
        google_role_fields = google_raw_role_string.split(
            AWS_GOOGLE_CONFIG_ROLE_SEPARATOR
        )
        google_role = google_role_fields[-1].split(AWS_GOOGLE_CONFIG_ROLE_PREFIX)[-1]
        account_id = google_role_fields[-2]
        original_env = AWS_ACCOUNT_TO_ENV[account_id][0]
        info = find_info(google_role)

        for azure_role in info["PERMISSION_SETS"]:
            raw_env, _ = azure_role.split("-")
            env = raw_env.lower()
            nickname = find_shortname(azure_role, key="AZURE_ROLE")
            azure_profile_name = f"profile dev-{env}-{nickname}"
            azure_profile = make_profile(azure_role, existing=new_profile.copy())
            if env == original_env:
                if not all(profile.get(k) == v for k, v in azure_profile.items()):
                    profile.update(azure_profile)
                    updated.add(azure_profile_name)
                if azure_profile_name in new_config:
                    del new_config[azure_profile_name]
                    created.remove(azure_profile_name)
                azure_profile_name = name
                azure_profile = profile
            elif (
                azure_profile_name not in existing_profiles
                and azure_role not in covered_roles
            ):
                created.add(azure_profile_name)
            else:
                continue

            covered_roles.add(azure_role)
            new_config[azure_profile_name] = azure_profile
        for prof in updated:
            print(
                f"[green]Updated [bold]{prof}[/] to map to {azure_role} permission set[/green]"
            )
        for prof in created:
            print(
                f"[green]Created new [b]{prof}[/] for {azure_role} permission set[/green]"
            )

    AWS_CFG.write_sections_to_file(sections=new_config, file=WriteableFiles.CONFIG)


RolesArg = typer.Argument(
    None,
    help="Should be a list of names of one or more AWS SSO permission sets, usually in the form {env}-{rolename},"
    + " e.g., QA-Developer. If adding QA-, Stage-, and Prod- for the same role, you can just list the role once with"
    + " `all` as the env, e.g., `all-{rolename}` to represent all three.",
)


@app.command()
def add_profiles(
    roles: list[str] = RolesArg,
    output_format: OutputFormats = OutputFormats.YAML.value,  # type: ignore[assignment]
    replace: bool = False,
):
    """Add a new profile in your AWS config for each of the role(s) provided.

    The resulting profile names will be in the form `dev[-{env}[-{role nickname}]]`, where -{env} is omitted for prod,
    and -{role nickname} is omitted for the first role in the list of roles passed in.
    """
    existing_config = AWS_CFG.profiles

    new_config = {
        "default": {"region": AWS_DEFAULT_REGION},
        "dev": {"region": AWS_DEFAULT_REGION},
    }

    for _role in roles:
        try:
            envs, role = expand_envs_from_role(_role)
        except BadEnvInRole as err:
            print(f"You requested a new profile for an unrecognized role ({_role})")
            raise typer.Exit(3) from err
        for _env in envs:
            new_profile = new_profile_from_base(output=output_format)
            env = _env.lower()
            print(env)
            nickname = find_shortname(role, key="AZURE_ROLE")
            profile_name = "profile dev" if env == "prod" else f"profile dev-{env}"
            if (
                profile_name in existing_config
                and existing_config[profile_name][AWS_SSO_ROLE_KEY]
                != new_profile[AWS_SSO_ROLE_KEY]
            ):
                profile_name += f"-{nickname}"
                print(f"exists, added {nickname} ({profile_name})")
                if profile_name in existing_config:
                    if not replace:
                        print(
                            f"Warning: {profile_name} exists in your config already. The existing profile will not be"
                            + " changed. Use --replace/-r to overwrite."
                        )
                        continue
                    else:
                        print(
                            f"Warning: {profile_name} exists in your config already. You specified --replace/-r, so the"
                            + " existing profile will overwritten."
                        )
            if (
                profile_name in new_config
                and new_profile[AWS_SSO_ROLE_KEY]
                != new_config[profile_name][AWS_SSO_ROLE_KEY]
            ):
                if nickname not in profile_name:
                    print(
                        f"{profile_name.capitalize()} created already, adding {nickname}"
                    )
                    profile_name += f"-{nickname}"
                else:
                    suffix = get_arbitrary_suffix(profile_name)
                    print(
                        f"Warning: profile name clash for {profile_name}, adding arbitrary suffix -{suffix}"
                    )
                    profile_name += f"-{suffix}"
            print(f"final: {profile_name}")
            print(f"{_env}-{role}")
            print(new_profile)
            profile = make_profile(f"{_env}-{role}", existing=new_profile)
            print(profile)
            new_config[profile_name] = profile
        existing_config.update(new_config)
    AWS_CFG.write_sections_to_file(sections=existing_config, file=WriteableFiles.CONFIG)


@app.command()
def new(
    output_format: OutputFormats = OutputFormats.YAML.value,  # type: ignore[assignment]
    destroy_existing: bool = typer.Option(  # noqa: B008
        False,
        "--destroy-existing",
        "-f",
        help=f"Replace your existing config file with new one. Existing will be backed up to config.{BACKUP_SUFFIX}",
    ),
    role: str = DEFAULT_ROLE,
):
    """Create a new config file with ROLE (default: all-Developer)."""
    config = {
        "default": {
            "region": AWS_DEFAULT_REGION,
        },
        "dev": {
            "region": AWS_DEFAULT_REGION,
        },
    }
    envs, role = expand_envs_from_role(role)
    profiles_created = []
    for _env in envs:
        env = _env.lower()
        base_profile_name = f"dev-{env}"
        if env == "prod":
            base_profile_name = f"dev"
        profile_name = f"profile {base_profile_name}"
        config[profile_name] = make_profile(
            f"{_env}-{role}",
            existing=new_profile_from_base(output=output_format),
        )
        profiles_created.append(base_profile_name)
    try:
        AWS_CFG.write_sections_to_file(
            sections=config, file=WriteableFiles.CONFIG, overwrite=destroy_existing
        )
        profiles_created = sorted(profiles_created)
        profiles_created[-1] = f"and {profiles_created[-1]}"
        print(f"Created profiles {', '.join(profiles_created)}")
    except FileExistsError:
        print(
            "Failure: file already exists. Specify --destroy-existing/-f to overwrite."
        )
        raise typer.Exit(1)


@app.command()
def make_primary(profile_name: str, env: CoreEnv = CoreEnv.PROD.value):  # type: ignore[assignment]
    """Renames a given (set of) profile(s) to dev[-{env}]. If env is `all`, profile_name must also contain `-all` which
    will be replaced by `-{env}` for non-prod profile names, but omitted for prod"""
    if profile_name == "dev":
        print("That profile is already your primary profile")
        raise typer.Exit()
    config = AWS_CFG.as_dict()
    if env == "all":
        if "-all" not in profile_name:
            print("Profile name must contain the string all- when env is all")
            raise typer.Exit(1)
        envs = ALL_CORE_ENVS
    else:
        envs = [env]
    for _env in envs:
        env_lower = _env.lower()
        if env_lower.lower() == "prod":
            target_name = "dev"
            previous_name = profile_name.replace("-?", f"")
        else:
            previous_name = profile_name.replace("-?", f"-{env_lower}")
            target_name = f"dev-{env_lower}"
        try:
            print(f"Renaming {previous_name} to {target_name}")
            rename(
                target=target_name,
                source=previous_name,
                existing_profiles=config,
            )
        except NoSuchProfile:
            print(
                f"Warning: could not find profile named {previous_name} to rename, skipping"
            )
    AWS_CFG.write_sections_to_file(sections=config, file=WriteableFiles.CONFIG)
    profiles = [
        f'{profile_name.removeprefix("profile ")}'
        + f' ({profile.get(AWS_SSO_ROLE_KEY, profile.get(AWS_GOOGLE_ROLE_KEY, "?"))})'
        for profile_name, profile in config.items()
        if profile_name.startswith("profile")
    ]
    profiles[-1] = f"and {profiles[-1]}"
    print(f"Your profiles: {', '.join(profiles)}")
