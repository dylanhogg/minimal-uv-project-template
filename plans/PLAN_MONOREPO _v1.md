# OLD v1 Plan: Migrate Cookiecutter Template to Monorepo Scaffolding

## Objective

Evolve this template from generating a single-package `src` layout to generating a uv-based monorepo scaffold, while keeping root template infrastructure stable and preserving testable template parity.

## Scope

In scope:

- Root template plumbing: `cookiecutter.json`, `hooks/`, `tests/template/`, root docs.
- Generated project template under `{{cookiecutter.project_slug}}/`.
- CI/dev tooling inside the generated template.

Out of scope:

- Adding runtime artifacts to root.
- Large behavioral changes unrelated to monorepo scaffolding.

## Current-State Constraints (What is coupled to single-package layout)

- Hooks require `src/{{cookiecutter.package_name}}/app.py` and `tests/{{cookiecutter.package_name}}/test_app.py`.
- Template tests assert single-package file paths and package wiring in one root `pyproject.toml`.
- Generated project `pyproject.toml` contains one package, one entrypoint, single coverage source, single `pythonpath`.
- Dockerfile copies only `src/` and `tests/` from one package root.
- VS Code debug docs/script, Makefile targets, and README commands assume `python -m {{cookiecutter.package_name}}.app`.

## Target Design (Monorepo Scaffold)

Use a uv workspace monorepo with one starter app package and one starter shared library package.

Proposed generated structure:

- `pyproject.toml` (workspace root; shared tooling config)
- `uv.lock`
- `apps/{{cookiecutter.app_slug}}/pyproject.toml`
- `apps/{{cookiecutter.app_slug}}/src/{{cookiecutter.app_package}}/...`
- `apps/{{cookiecutter.app_slug}}/tests/...`
- `packages/{{cookiecutter.lib_slug}}/pyproject.toml`
- `packages/{{cookiecutter.lib_slug}}/src/{{cookiecutter.lib_package}}/...`
- `packages/{{cookiecutter.lib_slug}}/tests/...`
- optional shared tooling dirs (`scripts/`, `docs/`) at workspace root.

Design rules:

- Root `pyproject.toml` defines workspace members and shared tool configs (`ruff`, `pyright`, `pytest`, coverage policy).
- Each member package has its own `project` metadata and dependencies.
- App package depends on library package via workspace path/dependency.
- Commands run from workspace root (`uv sync --all-groups`, `uv run ...`) and target all members unless scoped.

## Template Variable Strategy

Add variables to support monorepo naming and future extension:

- `repo_layout`: `monorepo` (prepare for optional future `single` compatibility path).
- `app_slug`, `app_package`
- `lib_slug`, `lib_package`

Default derivation strategy:

- derive `app_*` from current `project_slug`/`package_name`.
- derive `lib_*` as a stable suffix form (for example `{{app_slug}}-core`, `{{app_package}}_core`).

Validation additions in `hooks/pre_gen_project.py`:

- slug/package regex checks for all new identifiers.
- conflict checks (app and lib names cannot collide).

## Migration Phases

### Phase 1: Finalize monorepo contract

- Choose whether to keep backward compatibility mode:
  - Option A: monorepo-only template (simpler, faster).
  - Option B: dual-mode (`single` + `monorepo`) with conditional scaffolding.
- Define canonical generated workspace tree and naming conventions.
- Decide location for root tests (`tests/` at root vs per-member only).

Exit criteria:

- One agreed-on generated tree and variable set documented.

### Phase 2: Introduce template context and hook validation

- Update `cookiecutter.json` with monorepo fields.
- Update `hooks/pre_gen_project.py` validations for new fields.
- Update `hooks/post_gen_project.py` required file checks to workspace paths.
- Update `hooks/validate_template.py` smoke checks to monorepo required files.

Exit criteria:

- Hooks fail fast on invalid monorepo naming and pass with defaults.

### Phase 3: Restructure generated template files

- Replace single-package `src/{{cookiecutter.package_name}}/...` with:
  - app package under `apps/...`
  - shared library under `packages/...`
- Split packaging metadata:
  - root workspace `pyproject.toml`
  - per-member package `pyproject.toml`
- Update app imports to consume shared library package.

Exit criteria:

- `uv sync --all-groups` succeeds in rendered project.
- App runs through workspace tooling.

### Phase 4: Update dev workflow and docs in generated template

- Update generated `Makefile` commands for workspace-aware execution.
- Update generated `README.md` quickstart and run/test instructions.
- Update generated `AGENTS.md` project-structure guidance for monorepo paths.
- Update VS Code launch script/docs module paths and `PYTHONPATH` guidance.

Exit criteria:

- Generated docs/commands match actual workspace behavior.

### Phase 5: Update generated CI, pre-commit, and Docker

- Update generated `.github/workflows/ci.yml` to run workspace checks.
- Ensure pre-commit hooks run from workspace root and cover all members.
- Update generated `Dockerfile`/`docker-compose.yml` to copy/install workspace members correctly.

Exit criteria:

- Rendered CI recipe passes locally-equivalent commands.
- Docker smoke still works for app and tests in monorepo layout.

### Phase 6: Upgrade template parity tests

- Rewrite `tests/template/test_cookiecutter_template.py` assertions to:
  - verify workspace file topology,
  - verify app->lib dependency wiring,
  - verify entrypoint/module paths,
  - verify coverage/typecheck/lint commands at workspace root.
- Keep and extend runtime smoke tests (`uv sync`, `ruff`, `pyright`, `pytest`, CLI run).
- Add at least one test for customized app/lib naming context.

Exit criteria:

- `make template-test` passes against monorepo scaffold.

### Phase 7: Root docs and release readiness

- Update root `README.md` to describe monorepo output and variables.
- Ensure root `Makefile` validation targets remain unchanged unless necessary.
- Run full validation sequence:
  - `make template-test`
  - `make template-precommit`
  - `make template-docker-smoke`

Exit criteria:

- All root validations pass.
- No unresolved cookiecutter tokens in rendered output.

## File Impact Map

Root repo files expected to change:

- `cookiecutter.json`
- `hooks/pre_gen_project.py`
- `hooks/post_gen_project.py`
- `hooks/validate_template.py`
- `tests/template/test_cookiecutter_template.py`
- `README.md` (root template docs)
- `plans/PLAN_MONOREPO.md` (this plan)

Generated template files expected to change:

- `{{cookiecutter.project_slug}}/pyproject.toml`
- `{{cookiecutter.project_slug}}/README.md`
- `{{cookiecutter.project_slug}}/Makefile`
- `{{cookiecutter.project_slug}}/Dockerfile`
- `{{cookiecutter.project_slug}}/docker-compose.yml`
- `{{cookiecutter.project_slug}}/.github/workflows/ci.yml`
- `{{cookiecutter.project_slug}}/.pre-commit-config.yaml` (if scope or commands change)
- `{{cookiecutter.project_slug}}/AGENTS.md`
- `{{cookiecutter.project_slug}}/scripts/vscode_launch.sh`
- `{{cookiecutter.project_slug}}/docs/template/vscode-debug-setup.md`
- remove or relocate existing single-package `src/` and `tests/` content.

## Risks and Mitigations

Risk: uv workspace behavior differs from current single-package assumptions.

- Mitigation: lock contract early in Phase 1, then encode with tests before broad refactors.

Risk: Tooling configs (`pyright`, pytest, coverage) become inconsistent across packages.

- Mitigation: centralize shared tool config at workspace root and test for expected paths.

Risk: Docker and CI regress due to changed paths.

- Mitigation: keep smoke tests and CI command parity in template tests and docker smoke target.

Risk: Template complexity grows too much.

- Mitigation: prefer monorepo-only mode first; add dual-mode later only if required.

## Recommended Execution Order

1. Phase 1 contract decisions.
2. Phase 2 variables/hooks.
3. Phase 3 template tree + package metadata.
4. Phase 6 tests (early, before polishing docs).
5. Phase 4 and 5 tooling/docs alignment.
6. Phase 7 full validation and cleanup.

## Definition of Done

- Rendering default template produces a working uv workspace monorepo scaffold.
- Rendered app imports and runs against rendered shared library package.
- Root template tests and smoke targets pass.
- Root and generated docs accurately describe monorepo usage.
