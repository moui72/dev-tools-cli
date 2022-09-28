import typer

from cli.sso.manage_config import app as config_app
from cli.sso.utils import generate_credentials_file

app = typer.Typer()

app.add_typer(config_app, name="config", help="Manage your AWS SSO configuration")


@app.command()
def login():
    """Authenticate with AWS SSO and generate a credentials file (used automatically in many docker containers)"""
    bytes_written, credentials, errors = generate_credentials_file()
    profile_names = [p for p in credentials]
    if len(profile_names) > 1:
        profile_names[-1] = f"and {profile_names[-1]}"
    if len(profile_names) > 0:
        print(
            f"Saved credentials for {', '.join(profile_names)} (file size: {bytes_written} bytes)"
        )
    else:
        raise typer.Exit("No valid profiles")
    for profile, error in errors.items():
        print(f"Could not get credentials for {profile}: {error}")
