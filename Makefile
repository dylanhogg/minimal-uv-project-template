.EXPORT_ALL_VARIABLES:
DEV=True

venv:
	# Install https://github.com/astral-sh/uv on macOS and Linux:
	# $ curl -LsSf https://astral.sh/uv/install.sh | sh
	# Other recommended libraries, add with `uv add <library>`:
	# tenacity, joblib, jupyterlab, litellm, datasets, pytorch, fastapi, uvicorn, rich
	uv sync
	uv pip install -e .

which-python:
	uv run which python | pbcopy
	uv run which python

clean:
	rm -rf .venv

run:
	uv run python -m my_project.app reqarg1 --optional-arg "optional arg"

run-as-tool:
	uv run app reqarg1 --optional-arg "optional arg"

test:
	uv run pytest -vv --capture=no tests

manual-checks:
	uv run ruff format .
	uv run ruff check . --fix
	uv run pyright

precommit-install:
	# One time: Install git hook to run pre-commit automatically on git commit
	# Uninstall with: uv run pre-commit uninstall
	uv run pre-commit install

precommit:
	uv run pre-commit run --all-files

.DEFAULT_GOAL := help
.PHONY: help
help:
	@LC_ALL=C $(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'
