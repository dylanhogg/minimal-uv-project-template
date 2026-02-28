# PR2 Plan: Runtime Parity + CI Enforcement

## Goal
Enforce runtime parity for generated projects and harden template verification in CI, based on the completed PR1 Cookiecutter conversion.

## Scope
- Add template verification tests that render and validate generated projects.
- Extend existing root Template CI (do not add duplicate workflows).
- Enforce Docker parity as a required check on Ubuntu CI.
- Keep macOS CI parity checks for non-Docker validation.
- Pin Cookiecutter version in CI render steps (match local pre-commit behavior).

## Test Plan
1. Add template-level tests (pytest) that render cookiecutter projects in temp dirs for:
- Default config.
- Custom `project_slug` with derived default `package_name`.
- Custom `project_slug` with explicit `package_name` override.

2. Required assertions:
- Expected files exist (Docker and GitHub Actions files present).
- No unrendered `{{ cookiecutter.* }}` tokens remain.
- `pyproject.toml` reflects chosen variables.
- Import/module paths match `package_name`, including override case.

3. Required smoke commands on rendered output:
- `uv sync --all-groups`
- `uv run app reqarg1 --optional-arg optarg1`
- `uv run python -m {{cookiecutter.package_name}}.app reqarg1 --optional-arg optarg1`
- `uv run pytest -q tests`
- `docker compose run --rm app reqarg1 --optional-arg optarg1` (Ubuntu CI job)

## CI Plan
1. Extend existing root workflow [`.github/workflows/ci.yml`](minimal-uv-project-template/.github/workflows/ci.yml):
- Keep `ubuntu-latest` and `macos-latest` matrix for template validation.
- Keep hook compile and render smoke coverage.
- Add/keep rendered-project parity checks aligned with tests.

2. Lockfile behavior in CI:
- First run `uv sync --all-groups` to refresh for rendered metadata.
- Then run `uv sync --frozen --all-groups` for reproducibility checks.

3. Version pinning:
- Pin Cookiecutter version in CI render steps (same version as pre-commit smoke hook).

4. Docker parity:
- Mandatory required check on Ubuntu CI.
- macOS job continues non-Docker render/runtime parity checks.

## Definition of Done
- Generated projects pass `uv sync`, `ruff`, `pyright`, and `pytest`.
- CLI runtime parity passes for:
  - `uv run app ...`
  - `uv run python -m <package>.app ...`
- Docker Compose runtime parity check passes on Ubuntu CI.
- VSCode module path references remain correct in generated docs/scripts.
- No unrendered Cookiecutter tokens remain in generated projects.

## Suggested Commit Sequence
1. `test(template): add rendered-project parity tests (default + custom + override)`
2. `ci(template): extend root template CI and enforce ubuntu docker parity`
3. `chore(template): pin cookiecutter version consistently in CI and local smoke checks`
