# Minimal UV Project Template (Cookiecutter)

A minimal quick-start Python project template powered by [Cookiecutter](https://cookiecutter.readthedocs.io/), using [uv](https://github.com/astral-sh/uv) and a [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).

This repository is the template source. Running Cookiecutter generates a new runnable project with the same behavior as the original template.

## Generated Project Stack

Generated projects use the following libraries by default:

- APP - https://github.com/tiangolo/typer - CLI app framework
- APP - https://github.com/Delgan/loguru - logging
- APP - https://github.com/theskumar/python-dotenv - `.env` loading
- APP - https://github.com/pydantic/pydantic - data validation
- DEV - https://github.com/astral-sh/uv - package and environment management
- DEV - https://github.com/astral-sh/ruff - linting and formatting
- DEV - https://github.com/microsoft/pyright - type checking
- DEV - https://github.com/pytest-dev/pytest - tests
- DEV - https://github.com/pytest-dev/pytest-cov - test coverage
- DEV - https://github.com/pre-commit/pre-commit - git hooks

Generated projects also include:

- Docker (`Dockerfile`, `docker-compose.yml`)
- GitHub Actions CI
- VS Code launch helper (`scripts/vscode_launch.sh`)

Primary target platform is macOS and Linux.

## Scaffold A New Project

From this local repo:

```bash
uvx cookiecutter==2.6.0 .
```

From GitHub:

```bash
uvx cookiecutter==2.6.0 https://github.com/dylanhogg/minimal-uv-project-template.git
```

Non-interactive with defaults:

```bash
uvx cookiecutter==2.6.0 . --no-input -o /tmp
```

## Template Variables

- `project_name`: Human-readable name (example: `Awesome Stuff`)
- `project_slug`: Filesystem/project id, default derived from `project_name`
- `package_name`: Python package/module name, default `project_slug.replace('-', '_')`
- `project_short_description`: Short project summary
- `author_name`: Author display name
- `author_email`: Author email

Validation rules enforced at render time:

- `project_slug` must match `^[a-z][a-z0-9_-]*$`
- `package_name` must match `^[a-z][a-z0-9_]*$`

## Generated Project Quick Start

After scaffold:

```bash
cd <project_slug>
cp .env_template .env
uv sync --all-groups
uv pip install -e .
uv run app reqarg1 --optional-arg optarg1
uv run python -m <package_name>.app reqarg1 --optional-arg optarg1
uv run pytest -q tests
```

## Validate This Template Repo

Root Make targets:

```bash
make template-test           # render + parity tests
make template-precommit      # root pre-commit hooks
make template-docker-smoke   # docker parity smoke on generated output
make template-all            # all of the above
```

CI enforces template parity on macOS and Linux, with Docker parity smoke on Ubuntu.
