from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
from cookiecutter.exceptions import FailedHookException
from cookiecutter.main import cookiecutter

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from template_contract import required_project_paths


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
    required = required_project_paths(
        project_dir,
        app_slug=app_slug,
        app_package=app_package,
        lib_slug=lib_slug,
        lib_package=lib_package,
    )
    missing = [str(path.relative_to(project_dir)) for path in required if not path.exists()]
    assert not missing, f"Missing required files: {', '.join(missing)}"


def load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def assert_workspace_wiring(
    project_dir: Path,
    project_slug: str,
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> None:
    root_pyproject = load_toml(project_dir / "pyproject.toml")
    assert root_pyproject["project"]["name"] == f"{project_slug}-workspace"
    assert root_pyproject["tool"]["uv"]["workspace"]["members"] == ["apps/*", "packages/*"]
    assert ".cache" in root_pyproject["tool"]["ruff"]["extend-exclude"]
    assert ".venv" in root_pyproject["tool"]["ruff"]["extend-exclude"]

    pytest_addopts = root_pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    assert f"--cov={app_package}" in pytest_addopts
    assert f"--cov={lib_package}" in pytest_addopts
    assert root_pyproject["tool"]["coverage"]["run"]["source"] == [app_package, lib_package]

    app_pyproject = load_toml(project_dir / "apps" / app_slug / "pyproject.toml")
    assert app_pyproject["project"]["name"] == app_slug
    assert app_pyproject["project"]["scripts"]["app"] == f"{app_package}.app:app"
    assert lib_slug in app_pyproject["project"]["dependencies"]
    assert app_pyproject["tool"]["uv"]["sources"][lib_slug] == {"workspace": True}

    makefile_text = (project_dir / "Makefile").read_text(encoding="utf-8")
    assert f"uv run python -m {app_package}.app" in makefile_text

    vscode_script = (project_dir / "scripts" / "vscode_launch.sh").read_text(encoding="utf-8")
    assert f'"module": "{app_package}.app"' in vscode_script

    vscode_doc = (project_dir / "docs" / "template" / "vscode-debug-setup.md").read_text(encoding="utf-8")
    assert vscode_doc.count(f'"module": "{app_package}.app"') >= 2
    assert f"${{workspaceFolder}}/apps/{app_slug}/src" in vscode_doc
    assert f"${{workspaceFolder}}/packages/{lib_slug}/src" in vscode_doc


def runtime_env(project_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "UV_CACHE_DIR", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["UV_CACHE_DIR"] = str(project_dir / ".cache" / "uv")
    return env


def run_cmd(project_dir: Path, *cmd: str) -> None:
    proc = subprocess.run(cmd, cwd=project_dir, text=True, capture_output=True, env=runtime_env(project_dir))
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


@pytest.mark.parametrize(
    ("render_kwargs", "project_slug", "app_slug", "app_package", "lib_slug", "lib_package"),
    [
        ({}, "my-project", "my-project", "my_project", "my-project-core", "my_project_core"),
        ({"project_slug": "acme-tool"}, "acme-tool", "acme-tool", "acme_tool", "acme-tool-core", "acme_tool_core"),
        (
            {
                "project_slug": "acme-repo",
                "app_slug": "acme-cli",
                "app_package": "acme_cli",
                "lib_slug": "acme-shared",
                "lib_package": "acme_shared",
            },
            "acme-repo",
            "acme-cli",
            "acme_cli",
            "acme-shared",
            "acme_shared",
        ),
    ],
    ids=["default", "custom-project-slug", "custom-app-and-lib-overrides"],
)
def test_template_render_and_runtime(
    tmp_path: Path,
    render_kwargs: dict[str, str],
    project_slug: str,
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> None:
    project_dir = render_template(tmp_path, **render_kwargs)
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


def test_colliding_app_and_lib_slugs_fail_pre_gen(tmp_path: Path) -> None:
    with pytest.raises(FailedHookException):
        render_template(tmp_path, app_slug="same-name", lib_slug="same-name")
