# AGENTS Guidelines

This file contains guidelines for AI agents to follow when writing code in this project.

## Python Coding Guidelines

- Always be extremely concise. Sacrifice grammar for the sake of being concise.
- Write simple, clean and minimal code.
- Don't over complicate or over engineer solutions.
- Strive for simplicity and maintainability, while being efficient.
- Prefer implicit namespace packages and avoid creating __init__.py files unless there is a clear, justified need.
- Only update documentation or README.md if explicitly requested.
- Keep docstrings minimal, prefer the code to speak for itself.
- Keep functions small and focused on a single responsibility.
- Use asserts to check assumptions when appropriate.
- Use type hints for all function parameters and return values.
- Keep sensitive information in `.env` files.
- Provide meaningful error messages.
- Leverage `async` and `await` for I/O-bound operations to maximize concurrency.
- Leverage `asyncio` as an event-loop framework when appropriate.
- Use caching like `@functools.cache`, or `@functools.lru_cache`, when appropriate.
- For any pandas data pipelines, prefer chainable functions with `DataFrame.pipe(func, ...)`.
- Use f-strings for string formatting, and use the f"{var=}" syntax to show the variable name and its value.
- A functional programming approach is preferred over an object-oriented one. Use classes when appropriate.
- Use Pydantic data models when appropriate.

## Critical Thinking

- Fix root cause (not band-aid).
- If you are unsure: read more code; if still stuck, ask with short options.
- Prefer correct, maintainable implementations over clever, complex ones.
- If a popular, well tested library exists for a task, use it instead of reinventing the wheel.
- Be careful with secrets - do not expose them to the world (e.g. in logs, comments, git, etc.).

## Core Python Libraries to Use

- Use `typer` for building CLI applications
- Use `loguru` for all logging needs
- Use `pydantic` for data models and validation
- Use `python-dotenv` for environment variable management
- Use `ruff` for code formatting
- Use `pytest` for unit and integration tests

## Preferred Python Libraries, to install and use when Appropriate

- Use `pandas` for data processing
- Use `duckdb` for lightweight, in-memory database
- Use `numpy` for scientific computing
- Use `fastapi` for REST API endpoints
- Use `litellm` as an LLM wrapper
- Use `uvicorn` as an ASGI web server (and `uvloop` if approprite)
- Use `joblib` for lightweight pipelining & caching
- Use `pytorch` for machine learning
- Use `transformers` for nlp, llms, and models
- Use `datasets` for ready-to-use datasets for AI models
- Use `jupyterlab` or `marimo` for notebooks
- Use `streamlit` or `gradio` for demo apps
- Use `tenacity` for retrying function calls
- Use `rich` for formatting terminal output
- Use `pyarrow` for data serialization
- Use `arrow` for date and time conversions
- Use `requests` or `httpx` for HTTP communications

## Other Python Libraries to Consider

- Fall back to `scikit-learn` for machine learning if pytorch cannot be used
- Consider `joblib.Memory` for complex caching when `@functools.cache` is insufficient
- Consider `joblib.Parallel` for concurrency when appropriate
- Use `sqlalchemy` for SQL ORM when appropriate

## Project Structure

- Keep source code in a `./src/<package_name>/` directory.
- Place tests in a `./tests/<package_name>/` directory.
- Keep configuration files in the root directory.
- See below for more details on testing, linting, and type checking.
- See `Makefile` for additional project management commands.

## Package Management with uv

- Package management is via `uv`.
- Create venv and install deps with `uv sync`.
- Install project in editable mode with `uv pip install -e . --no-deps`.
- Manage dependencies via `pyproject.toml`, with dev dependencies in the `[dependency-groups]` section.
- Add runtime dependencies: `uv add <pkg>`.
- Add dev dependencies: `uv add --group dev <pkg>`.
- Sync lockfile: `uv sync`.

## Tests

- Use `pytest` for testing.
- Use `pytest-cov` for code coverage reporting.
- Follow the naming convention: test_*.py.
- Use fixtures for test setup and teardown.
- Place test files in `./tests/<package_name>/`.

## Linting

- Use `ruff` for formatting and linting.
- Run `uv run ruff format .` to format the code.
- Run `uv run ruff check . --fix` to check the code and fix any issues.

## Type Checking

- Use `pyright` for type checking.
- Run `uv run pyright` to type check the code.

## Docker

- Dockerfile is in the root directory
- Use `docker compose` for building and running the container.
- Build: `docker compose build`
- Run CLI: `docker compose run --rm app reqarg --optional-arg optarg`
- Run tests: `docker compose run --rm tests`
