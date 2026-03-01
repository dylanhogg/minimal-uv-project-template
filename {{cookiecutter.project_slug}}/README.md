# {{cookiecutter.project_name}}

{{cookiecutter.project_short_description}}

A minimal uv workspace monorepo with one app package and one shared library package.

Workspace layout:

- `apps/{{cookiecutter.app_slug}}` - CLI app package
- `packages/{{cookiecutter.lib_slug}}` - shared library package

Uses the following 3rd party libraries:

- APP - https://github.com/tiangolo/typer - For building CLI applications
- APP - https://github.com/Delgan/loguru - Python logging made (stupidly) simple
- APP - https://github.com/theskumar/python-dotenv - Reads key-value pairs `.env` file and sets environment vars
- APP - https://github.com/pydantic/pydantic - Data validation and settings management using Python type annotations
- DEV - https://github.com/astral-sh/uv - An extremely fast Python package manager
- DEV - https://github.com/astral-sh/ruff - Extremely fast Python linter and code formatter
- DEV - https://github.com/microsoft/pyright - Static type checker for Python
- DEV - https://github.com/pytest-dev/pytest - makes it easy to write small tests, yet scales to support complex functional testing
- DEV - https://github.com/pytest-dev/pytest-cov - Unit test coverage for pytest
- DEV - https://github.com/pre-commit/pre-commit - A framework for managing pre-commit hooks

Create virtual environment and install workspace dependencies with `uv sync --all-packages --all-groups`.

Pre-commit hooks require a one-time setup: `uv run pre-commit install`.

Run the app with:

- `uv run app reqarg1 --optional-arg optarg1`
- `uv run python -m {{cookiecutter.app_package}}.app reqarg1 --optional-arg optarg1`

See Makefile for quick utility commands for running the app, tests, type checking, and pre-commit hooks.

Includes an AGENTS.md file for high-signal agents guide for working in this repo.
