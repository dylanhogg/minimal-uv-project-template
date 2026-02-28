# Plan: Two-Stage PR Refactor to Cookiecutter Template

## Goal
Convert this copy/paste uv repo into a real Cookiecutter template repo that scaffolds production-ready Python projects with minimal prompts and strong defaults for macOS/Linux use.

## PR Scope
Two staged PRs:
- PR1: Mechanical Cookiecutter conversion.
- PR2: Runtime parity and CI enforcement.

## Target Outcome
- `cookiecutter <repo>` generates a runnable project with:
  - `uv sync`
  - `uv run ruff check .`
  - `uv run pyright`
  - `uv run pytest`
- Generated project keeps current quality baseline (src layout, typer CLI, loguru, dotenv, pydantic, pytest/ruff/pyright, Makefile, Docker, GitHub Actions).
- Template rendering works for macOS/Linux without bash-only generation assumptions.
- Generated project keeps runtime parity with source template:
  - same CLI entrypoints (`uv run app` and `python -m <package>.app`)
  - same Docker/Docker Compose run behavior
  - same pre-commit/CI check flow
  - same VSCode debug module wiring

## Proposed Template Variables (Balanced Coverage)
Use 6 variables (5 user inputs + 1 derived/locked value). Enough for identity/metadata; avoid feature toggles.

| Variable | Type | Default | Why |
|---|---|---|---|
| `project_name` | str | `My Project` | Human-readable project title |
| `project_slug` | str | `my-project` | Repo/package root folder name |
| `package_name` | str | `{{ cookiecutter.project_slug.replace('-', '_') }}` | Python import package (locked to derived default) |
| `project_short_description` | str | `My project description` | `pyproject.toml` metadata |
| `author_name` | str | `Your Name` | Package metadata |
| `author_email` | str | `you@example.com` | Package metadata |

## Implementation Plan
### PR1: Mechanical Cookiecutter Conversion
1. Create Cookiecutter repo shape.
- Add `cookiecutter.json`.
- Move current scaffold into `{{cookiecutter.project_slug}}/`.
- Keep template repo root clean: only template infra + meta files.

2. Parameterize project content.
- Replace hardcoded `my_project`/`my-project` occurrences with Jinja vars.
- Parameterize at minimum:
  - `pyproject.toml` project name, description, package/import paths, coverage source paths.
  - `src/{{cookiecutter.package_name}}/**` and `tests/{{cookiecutter.package_name}}/**`.
  - `README.md`, Docker/compose names, VSCode launch module path.
  - `scripts/vscode_launch.sh` module path.
  - `docs/template/vscode-debug-setup.md` module path examples.
  - Keep CLI entry as `app` and module as `{{cookiecutter.package_name}}.app` (same behavior as source template).

3. Lockfile parity on first generated run.
- First generated-run bootstrap uses `uv sync --all-groups` (not frozen) to refresh `uv.lock` for rendered metadata.
- After refresh, CI/runtime checks use `uv sync --frozen --all-groups` to preserve reproducibility.

4. Add robust hooks (Python, stdlib-only).
- `hooks/pre_gen_project.py`:
  - Validate slug/package patterns (`^[a-z][a-z0-9_-]*$` for slug, `^[a-z][a-z0-9_]*$` for package).
  - Enforce lock: `package_name` must equal `project_slug.replace('-', '_')`.
  - Fail fast with clear errors.
- `hooks/post_gen_project.py`:
  - Verify key files exist after render and fail with clear error if not.
  - Normalize any remaining template artifacts.

5. Cross-platform hardening.
- Remove macOS-only `pbcopy` usage from generated Makefile target; print path only.
- Ensure hook scripts use `pathlib`, not shell-specific commands.
- Keep line endings/tool configs portable (`line-ending = "auto"` already good).
- Avoid shell dependency in generation path; bash scripts can remain optional runtime helpers for macOS/Linux.

### PR2: Runtime Parity + CI Enforcement
6. Add template verification tests.
- Add template-level tests (pytest) that run cookiecutter generation in temp dirs for at least:
  - Default config.
  - Custom `project_slug` with derived `package_name`.
  - Negative case: custom `project_slug` + mismatched `package_name` fails pre-gen validation.
- Assertions:
  - Expected files exist (Docker and GitHub Actions always present).
  - No unrendered `{{ cookiecutter.* }}` remains.
  - Generated `pyproject.toml` reflects chosen vars.
  - Generated import paths and module references match `package_name`.
  - Smoke commands succeed in generated output:
    - `uv sync --all-groups`
    - `uv run app reqarg1 --optional-arg optarg1`
    - `uv run python -m {{cookiecutter.package_name}}.app reqarg1 --optional-arg optarg1`
    - `uv run pytest -q tests`
    - `docker compose run --rm app reqarg1 --optional-arg optarg1`

7. CI update for template repo.
- Add job to execute template tests on `ubuntu-latest` and `macos-latest`.
- Keep lint/type/tests for template code itself.
- In generated-project validation, run first `uv sync --all-groups` to refresh lockfile, then `uv sync --frozen --all-groups`.
- Docker parity is mandatory in CI: run generated-project Docker Compose smoke test in CI (required check).
- Do not run heavyweight network/install steps inside hooks.

8. Cleanup and guardrails.
- Exclude generated/runtime artifacts from template (`.venv`, caches, coverage, logs, egg-info, `__pycache__`).
- Ensure template root `.gitignore` and generated project `.gitignore` both correct.
- Keep defaults deterministic and fast.

## Definition of Done
- Cookiecutter generation succeeds on Linux/macOS.
- Generated project passes `uv sync`, `ruff`, `pyright`, `pytest`.
- Docker and GitHub Actions files are always present and valid.
- Generated runtime parity checks pass for CLI entrypoints, Docker Compose run path, and VSCode debug module paths.
- No hardcoded old package names remain.
- No bash-only generation dependency remains.

## Risks and Mitigations
- Risk: Over-templating increases maintenance.
  - Mitigation: Keep variable count fixed to 6, no feature matrix explosion.
- Risk: Cross-platform drift in scripts/paths.
  - Mitigation: Python hooks + macOS/Linux CI matrix.
- Risk: Broken imports after rename.
  - Mitigation: Automated render tests + grep check for stale names.

## Suggested PR Commit Sequence
1. `feat(template): create cookiecutter structure and parameterize scaffold`
2. `feat(template): add generation hooks and cross-platform hardening`
3. `test(template): add generated-project parity smoke tests`
4. `ci(template): enforce linux/macos template + docker parity checks`
5. `chore(template): remove non-template artifacts and finalize ignores`
