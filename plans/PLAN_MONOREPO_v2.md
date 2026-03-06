# OLD v2 Plan: Migrate Cookiecutter Template to Monorepo Scaffolding

## Objective

Evolve this template from generating a single-package `src` layout to generating a uv workspace monorepo scaffold, while keeping root template infrastructure stable and preserving testable parity.

## Scope

In scope:

- Root template plumbing: `cookiecutter.json`, `hooks/`, `tests/template/`, root docs.
- Generated project template under `{{cookiecutter.project_slug}}/`.
- Generated CI, pre-commit, Docker, docs, and developer workflows.

Out of scope:

- Adding runtime artifacts to root.
- Supporting both single-package and monorepo scaffolds in the same release.

## Current-State Constraints (Single-Package Coupling)

- Hooks require `src/{{cookiecutter.package_name}}/app.py` and `tests/{{cookiecutter.package_name}}/test_app.py`.
- Template tests assert single-package topology and root `pyproject.toml` wiring.
- Generated project has one package, one entrypoint, one coverage source, and one `pythonpath`.
- Dockerfile copies one `src/` and `tests/` tree.
- VS Code docs/script, Makefile, and README commands assume `python -m {{cookiecutter.package_name}}.app`.

## Monorepo Contract (Locked Decisions)

These decisions replace all Phase 1 open questions.

1. Compatibility and release:

- Adopt monorepo-only scaffold now.
- Do not add `single`/`monorepo` conditional logic in template files.
- Treat this as a breaking template change and release with a major version bump/tag.
- Keep previous template behavior available via an earlier tag/branch.

2. Canonical generated tree:

- Use uv workspace root with members in `apps/*` and `packages/*`.
- Scaffold exactly one starter app package and one starter shared library package.
- Keep shared operational docs/scripts at workspace root (`README.md`, `Makefile`, `scripts/`, `docs/`).

3. Test topology:

- Primary tests live with each member package (`apps/.../tests`, `packages/.../tests`).
- Keep root-level tests only for cross-package integration smoke if needed.
- Workspace commands run from root and discover member tests.

4. Tooling ownership:

- Root `pyproject.toml` owns shared tool config (`ruff`, `pyright`, `pytest`, `coverage`, `tool.uv.workspace`).
- Member `pyproject.toml` files own package metadata and package-specific dependencies.
- Prefer no member-level tool overrides unless required.

5. Dependency model:

- App package depends on shared library package via workspace dependency.
- Runtime dependencies belong to the owning member package.
- Dev tools remain managed centrally from workspace root.

6. Entrypoint and command model:

- App member exposes CLI script `app`.
- Library member exposes no CLI script.
- Standard commands (`uv sync --all-groups`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`) run at workspace root.

7. CI and Docker contract:

- Generated CI runs the same workspace-root commands used locally.
- Docker targets app execution and workspace-root test execution with monorepo paths.

## Target Design (Monorepo Scaffold)

Generated structure (contractual):

- `pyproject.toml` (workspace root; shared tooling config)
- `uv.lock`
- `apps/{{cookiecutter.app_slug}}/pyproject.toml`
- `apps/{{cookiecutter.app_slug}}/src/{{cookiecutter.app_package}}/...`
- `apps/{{cookiecutter.app_slug}}/tests/...`
- `packages/{{cookiecutter.lib_slug}}/pyproject.toml`
- `packages/{{cookiecutter.lib_slug}}/src/{{cookiecutter.lib_package}}/...`
- `packages/{{cookiecutter.lib_slug}}/tests/...`
- workspace root operational files: `README.md`, `Makefile`, `scripts/`, `docs/`, `.github/workflows/ci.yml`

## Template Variable Strategy (Locked)

Expose only monorepo-related names; do not add `repo_layout` yet.

Required template variables:

- `project_name`
- `project_slug`
- `project_short_description`
- `author_name`
- `author_email`
- `app_slug`
- `app_package`
- `lib_slug`
- `lib_package`

Default derivation strategy:

- `app_slug = project_slug`
- `app_package = project_slug.replace('-', '_')`
- `lib_slug = app_slug + "-core"`
- `lib_package = app_package + "_core"`

Validation rules in `hooks/pre_gen_project.py`:

- `project_slug`, `app_slug`, `lib_slug` must match `^[a-z][a-z0-9_-]*$`.
- `app_package`, `lib_package` must match `^[a-z][a-z0-9_]*$`.
- app/lib slug and package names must not collide.
- `author_email` validation remains unchanged.

## Implementation Stages (Multi-Stage, PR-Sized)

### Stage 1: Contract and variable plumbing

Changes:

- Update `cookiecutter.json` with `app_*` and `lib_*` defaults.
- Update hook validations and required-file checks for monorepo paths.
- Update `hooks/validate_template.py` smoke expectations.

Validation gate:

- `make template-test` passes hook and render smoke portions.

### Stage 2: Scaffold filesystem and package metadata

Changes:

- Replace single-package tree with `apps/` and `packages/` members.
- Create root workspace `pyproject.toml` and member `pyproject.toml` files.
- Wire app imports to consume shared library member.

Validation gate:

- Rendered output has expected topology.
- `uv sync --all-groups` succeeds in rendered project.

### Stage 3: Workspace tooling alignment

Changes:

- Update generated `Makefile`, `.pre-commit-config.yaml`, and VS Code launch/docs.
- Ensure commands are workspace-root and member-aware.
- Align pytest/coverage/pyright settings with workspace paths.

Validation gate:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest -q`

### Stage 4: CI and Docker parity

Changes:

- Update generated `.github/workflows/ci.yml` to run workspace commands.
- Update generated `Dockerfile` and `docker-compose.yml` for monorepo paths.

Validation gate:

- `make template-docker-smoke` passes.
- Generated CI command sequence mirrors local sequence.

### Stage 5: Template parity tests upgrade

Changes:

- Rewrite `tests/template/test_cookiecutter_template.py` for monorepo assertions:
  - topology contract,
  - app->lib wiring,
  - command/runtime smoke,
  - custom naming context render.

Validation gate:

- `make template-test` passes end to end.

### Stage 6: Documentation and release prep

Changes:

- Update root `README.md` and generated `README.md`/`AGENTS.md`.
- Confirm root Make targets remain stable.
- Add migration notes referencing previous tag for single-package consumers.

Validation gate:

- `make template-test`
- `make template-precommit`
- `make template-docker-smoke`

## File Impact Map

Root files expected to change:

- `cookiecutter.json`
- `hooks/pre_gen_project.py`
- `hooks/post_gen_project.py`
- `hooks/validate_template.py`
- `tests/template/test_cookiecutter_template.py`
- `README.md`
- `plans/PLAN_MONOREPO.md`

Generated template files expected to change:

- `{{cookiecutter.project_slug}}/pyproject.toml` (workspace root format)
- `{{cookiecutter.project_slug}}/README.md`
- `{{cookiecutter.project_slug}}/Makefile`
- `{{cookiecutter.project_slug}}/Dockerfile`
- `{{cookiecutter.project_slug}}/docker-compose.yml`
- `{{cookiecutter.project_slug}}/.github/workflows/ci.yml`
- `{{cookiecutter.project_slug}}/.pre-commit-config.yaml`
- `{{cookiecutter.project_slug}}/AGENTS.md`
- `{{cookiecutter.project_slug}}/scripts/vscode_launch.sh`
- `{{cookiecutter.project_slug}}/docs/template/vscode-debug-setup.md`
- remove/relocate existing single-package `src/` and `tests/` to `apps/` and `packages/`.

## Risks and Mitigations

Risk: uv workspace behavior diverges from current assumptions.

- Mitigation: lock contract first, then encode topology and runtime checks in template tests.

Risk: Tooling drift across workspace members.

- Mitigation: centralize tool config at workspace root and avoid member overrides.

Risk: CI/Docker regressions from path changes.

- Mitigation: keep local and CI command parity; retain docker smoke validation target.

Risk: Upgrade friction for existing users.

- Mitigation: major-version release and explicit reference to prior single-package tag.

## Stage Order (Recommended)

1. Stage 1 contract and hooks.
2. Stage 2 scaffold topology and metadata.
3. Stage 5 parity tests (early lock-in of behavior).
4. Stage 3 tooling alignment.
5. Stage 4 CI/Docker parity.
6. Stage 6 docs and release prep.

## Definition of Done

- Rendering default template produces a working uv workspace monorepo scaffold.
- App member imports and runs against shared library member.
- Root template validations pass (`template-test`, `template-precommit`, `template-docker-smoke`).
- Root and generated docs accurately describe monorepo usage and commands.
