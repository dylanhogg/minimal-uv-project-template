# AGENTS (Root Repo)

This `AGENTS.md` applies to the Cookiecutter template repository root, not generated projects.

## Scope
- Maintain template infrastructure in root:
  - `cookiecutter.json`
  - `hooks/`
  - root CI / pre-commit / Makefile
  - `tests/template/`
- Template project files live under:
  - `{{cookiecutter.project_slug}}/`

## Rules
- Keep root changes minimal and template-focused.
- Do not add generated-project runtime artifacts to root.
- Prefer updating template tests when changing hooks/render behavior.

## Local Validation
- `make template-test`
- `make template-precommit`
- `make template-docker-smoke` (when Docker validation is needed)

## Notes
- Root CI validates template rendering/parity.
- Generated-project CI config is templated inside `{{cookiecutter.project_slug}}/.github/workflows/ci.yml`.
