# minimal-uv-project-template

A minimal quick-start Python project template, using [uv](https://github.com/astral-sh/uv) package manager and a [src](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) layout.

Uses the following 3rd party libraries:

- APP - https://github.com/tiangolo/typer - For building CLI applications
- APP - https://github.com/Delgan/loguru - Python logging made (stupidly) simple
- APP - https://github.com/theskumar/python-dotenv - Reads key-value pairs `.env` file and sets environment vars
- APP - https://github.com/pydantic/pydantic - Data validation and settings management using Python type annotations
- DEV - https://github.com/astral-sh/uv - An extremely fast Python package manager
- DEV - https://github.com/astral-sh/ruff - Extremely fast Python linter and code formatter
- DEV - https://github.com/microsoft/pyright - Static type checker for Python
- DEV - https://github.com/pytest-dev/pytest - makes it easy to write small tests, yet scales to support complex functional testing
- DEV - https://github.com/pre-commit/pre-commit - A framework for managing pre-commit hooks

Create venv virtual environment with `uv sync`

Pre-commit hooks require a one-time setup: `uv run pre-commit install`

See Makefile for quick utility commands for creation of venv, running the app, running tests, typechecking, pre-commit hooks etc.

Includes an AGENTS.md file for high-signal agents guide for working in this repo.
