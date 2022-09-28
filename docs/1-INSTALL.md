# Installing

## Infra

This tool relies on AWS infrastructure, which has not been well abstracted out. This repo is intended for educational purposes, so you're mostly on your own for setting up the infra, though a terraform module is included (see `infra/` in the source code).

## CLI

You can install this tool from the git repo using `pip`. You can also install it from the git repo via poetry, but there are [some caveates](#via-poetry) if you install that way.

### Via Git

You can clone this repo, and then install the CLI via pip

1. clone repo: `gh repo clone moui72/dev-tools` or `git clone git@github.com:moui72/dev-tools.git`
1. from within the repo directory, install via pip with `pip install --editable .`[^editable]

### Via poetry

You can also install this application via [poetry](https://python-poetry.org/) rather than `pip`, but doing so will make it isolated to a virtual environment and therefore not globally available via the `dev` command, while the rest of this documentation assumes it is globally available.

If you choose to use poetry, be aware that all `dev ...` commands must be run from within the poetry-created venv, i.e., from within the project directory via `poetry run dev ...`.

1. clone repo: `gh repo clone moui72/dev-tools` or `git clone git@github.com:moui72/dev-tools.git`
1. from within the repo directory, install via poetry `poetry install`

[^editable]: The `--editable` option with `pip install` allows changes made to the source code to be immediately reflected on execution, without having to rebuild the package
