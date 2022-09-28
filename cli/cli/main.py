from logging import INFO, getLogger

import typer

from cli.parameter_store import app as param_store
from cli.sso import app as sso

logger = getLogger()
logger.setLevel(INFO)

app = typer.Typer()
app.add_typer(
    param_store,
    name="params",
    help="Request changes to parameter store values or review requests",
)
app.add_typer(sso, name="sso", help="Manage your aws credentials")
