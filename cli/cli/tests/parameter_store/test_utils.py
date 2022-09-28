import pytest

from cli.parameter_store.exceptions import InvalidParameterPathError
from cli.parameter_store.utils import ENVIRONMENTS, get_env

bad_paths = [
    "{env}/something",
    "{env}-something",
    "{env}",
    "/something/{env}/something",
    "/{env}-something/something",
]


@pytest.mark.parametrize(
    "path",
    [template.format(env=ENVIRONMENTS[i]) for i, template in enumerate(bad_paths)],
)
def test_get_env__raises(path):
    with pytest.raises(InvalidParameterPathError):
        get_env(path)


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_get_env__success(env):
    assert get_env(f"/{env}/abc/etc") == env
