from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from cookiecutter.exceptions import FailedHookException
from cookiecutter.main import cookiecutter


def render_template(tmp_path: Path, **extra_context: str) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    rendered = cookiecutter(
        str(repo_root),
        no_input=True,
        output_dir=str(tmp_path),
        overwrite_if_exists=True,
        extra_context=extra_context or None,
    )
    return Path(rendered)


def assert_no_unrendered_tokens(project_dir: Path) -> None:
    unresolved: list[str] = []
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "{{ cookiecutter." in text or "{{cookiecutter." in text:
            unresolved.append(str(path.relative_to(project_dir)))
    assert not unresolved, f"Unrendered cookiecutter tokens in: {', '.join(unresolved[:8])}"


def assert_expected_files(
    project_dir: Path,
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> None:
    required = [
        project_dir / ".github" / "workflows" / "ci.yml",
        project_dir / ".pre-commit-config.yaml",
        project_dir / "Dockerfile",
        project_dir / "docker-compose.yml",
        project_dir / "pyproject.toml",
        project_dir / "scripts" / "vscode_launch.sh",
        project_dir / "docs" / "template" / "vscode-debug-setup.md",
        project_dir / "apps" / app_slug / "pyproject.toml",
        project_dir / "apps" / app_slug / "src" / app_package / "app.py",
        project_dir / "apps" / app_slug / "tests" / "test_app.py",
        project_dir / "packages" / lib_slug / "pyproject.toml",
        project_dir / "packages" / lib_slug / "src" / lib_package / "env.py",
        project_dir / "packages" / lib_slug / "src" / lib_package / "log.py",
        project_dir / "packages" / lib_slug / "tests" / "test_env.py",
        project_dir / "packages" / lib_slug / "tests" / "test_log.py",
    ]
    missing = [str(path.relative_to(project_dir)) for path in required if not path.exists()]
    assert not missing, f"Missing required files: {', '.join(missing)}"


def assert_workspace_wiring(
    project_dir: Path,
    project_slug: str,
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> None:
    root_pyproject = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert f'name = "{project_slug}-workspace"' in root_pyproject
    assert 'members = ["apps/*", "packages/*"]' in root_pyproject
    assert f'--cov={app_package}' in root_pyproject
    assert f'--cov={lib_package}' in root_pyproject
    assert f'source = ["{app_package}", "{lib_package}"]' in root_pyproject

    app_pyproject = (project_dir / "apps" / app_slug / "pyproject.toml").read_text(encoding="utf-8")
    assert f'name = "{app_slug}"' in app_pyproject
    assert f'app = "{app_package}.app:app"' in app_pyproject
    assert f'"{lib_slug}"' in app_pyproject
    assert f'"{lib_slug}" = {{ workspace = true }}' in app_pyproject

    makefile_text = (project_dir / "Makefile").read_text(encoding="utf-8")
    assert f"uv run python -m {app_package}.app" in makefile_text

    vscode_script = (project_dir / "scripts" / "vscode_launch.sh").read_text(encoding="utf-8")
    assert f'"module": "{app_package}.app"' in vscode_script

    vscode_doc = (project_dir / "docs" / "template" / "vscode-debug-setup.md").read_text(encoding="utf-8")
    assert vscode_doc.count(f'"module": "{app_package}.app"') >= 2
    assert f"${{workspaceFolder}}/apps/{app_slug}/src" in vscode_doc
    assert f"${{workspaceFolder}}/packages/{lib_slug}/src" in vscode_doc


def run_cmd(project_dir: Path, *cmd: str) -> None:
    proc = subprocess.run(cmd, cwd=project_dir, text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def smoke_test_runtime(project_dir: Path, app_package: str) -> None:
    run_cmd(project_dir, "uv", "sync", "--all-packages", "--all-groups")
    run_cmd(project_dir, "uv", "run", "ruff", "check", ".")
    run_cmd(project_dir, "uv", "run", "pyright")
    run_cmd(project_dir, "uv", "run", "app", "reqarg1", "--optional-arg", "optarg1")
    run_cmd(
        project_dir,
        "uv",
        "run",
        "python",
        "-m",
        f"{app_package}.app",
        "reqarg1",
        "--optional-arg",
        "optarg1",
    )
    run_cmd(project_dir, "uv", "run", "pytest", "-q")


def test_default_template_render_and_runtime(tmp_path: Path) -> None:
    project_dir = render_template(tmp_path)
    project_slug = "my-project"
    app_slug = "my-project"
    app_package = "my_project"
    lib_slug = "my-project-core"
    lib_package = "my_project_core"

    assert_expected_files(project_dir, app_slug, app_package, lib_slug, lib_package)
    assert_no_unrendered_tokens(project_dir)
    assert_workspace_wiring(project_dir, project_slug, app_slug, app_package, lib_slug, lib_package)
    smoke_test_runtime(project_dir, app_package)


def test_custom_slug_derived_app_and_lib_names(tmp_path: Path) -> None:
    project_slug = "acme-tool"
    app_slug = "acme-tool"
    app_package = "acme_tool"
    lib_slug = "acme-tool-core"
    lib_package = "acme_tool_core"
    project_dir = render_template(tmp_path, project_slug=project_slug)

    assert_expected_files(project_dir, app_slug, app_package, lib_slug, lib_package)
    assert_no_unrendered_tokens(project_dir)
    assert_workspace_wiring(project_dir, project_slug, app_slug, app_package, lib_slug, lib_package)
    smoke_test_runtime(project_dir, app_package)


def test_custom_app_and_lib_overrides(tmp_path: Path) -> None:
    project_slug = "acme-repo"
    app_slug = "acme-cli"
    app_package = "acme_cli"
    lib_slug = "acme-shared"
    lib_package = "acme_shared"
    project_dir = render_template(
        tmp_path,
        project_slug=project_slug,
        app_slug=app_slug,
        app_package=app_package,
        lib_slug=lib_slug,
        lib_package=lib_package,
    )

    assert_expected_files(project_dir, app_slug, app_package, lib_slug, lib_package)
    assert_no_unrendered_tokens(project_dir)
    assert_workspace_wiring(project_dir, project_slug, app_slug, app_package, lib_slug, lib_package)
    smoke_test_runtime(project_dir, app_package)


def test_invalid_author_email_fails_pre_gen(tmp_path: Path) -> None:
    with pytest.raises(FailedHookException):
        render_template(tmp_path, author_email="not-an-email")


def test_colliding_app_and_lib_packages_fail_pre_gen(tmp_path: Path) -> None:
    with pytest.raises(FailedHookException):
        render_template(tmp_path, app_package="same_name", lib_package="same_name")
