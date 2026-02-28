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


def assert_expected_files(project_dir: Path, package_name: str) -> None:
    required = [
        project_dir / ".github" / "workflows" / "ci.yml",
        project_dir / ".pre-commit-config.yaml",
        project_dir / "Dockerfile",
        project_dir / "docker-compose.yml",
        project_dir / "pyproject.toml",
        project_dir / "scripts" / "vscode_launch.sh",
        project_dir / "docs" / "template" / "vscode-debug-setup.md",
        project_dir / "src" / package_name / "app.py",
        project_dir / "tests" / package_name / "test_app.py",
    ]
    missing = [str(path.relative_to(project_dir)) for path in required if not path.exists()]
    assert not missing, f"Missing required files: {', '.join(missing)}"


def assert_package_wiring(project_dir: Path, project_slug: str, package_name: str) -> None:
    pyproject_text = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert f'name = "{project_slug}"' in pyproject_text
    assert f'app = "{package_name}.app:app"' in pyproject_text
    assert f'--cov={package_name}' in pyproject_text
    assert f'source = ["{package_name}"]' in pyproject_text
    assert f'source = ["src/{package_name}"]' in pyproject_text

    makefile_text = (project_dir / "Makefile").read_text(encoding="utf-8")
    assert f"uv run python -m {package_name}.app" in makefile_text

    vscode_script = (project_dir / "scripts" / "vscode_launch.sh").read_text(encoding="utf-8")
    assert f'"module": "{package_name}.app"' in vscode_script

    vscode_doc = (project_dir / "docs" / "template" / "vscode-debug-setup.md").read_text(encoding="utf-8")
    assert vscode_doc.count(f'"module": "{package_name}.app"') >= 2


def run_cmd(project_dir: Path, *cmd: str) -> None:
    proc = subprocess.run(cmd, cwd=project_dir, text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def smoke_test_runtime(project_dir: Path, package_name: str) -> None:
    run_cmd(project_dir, "uv", "sync", "--all-groups")
    run_cmd(project_dir, "uv", "sync", "--frozen", "--all-groups")
    run_cmd(project_dir, "uv", "run", "ruff", "check", ".")
    run_cmd(project_dir, "uv", "run", "pyright")
    run_cmd(project_dir, "uv", "run", "app", "reqarg1", "--optional-arg", "optarg1")
    run_cmd(
        project_dir,
        "uv",
        "run",
        "python",
        "-m",
        f"{package_name}.app",
        "reqarg1",
        "--optional-arg",
        "optarg1",
    )
    run_cmd(project_dir, "uv", "run", "pytest", "-q", "tests")


def test_default_template_render_and_runtime(tmp_path: Path) -> None:
    project_dir = render_template(tmp_path)
    package_name = "my_project"
    project_slug = "my-project"

    assert_expected_files(project_dir, package_name)
    assert_no_unrendered_tokens(project_dir)
    assert_package_wiring(project_dir, project_slug, package_name)
    smoke_test_runtime(project_dir, package_name)


def test_custom_slug_derived_package(tmp_path: Path) -> None:
    project_slug = "acme-tool"
    package_name = "acme_tool"
    project_dir = render_template(tmp_path, project_slug=project_slug)

    assert_expected_files(project_dir, package_name)
    assert_no_unrendered_tokens(project_dir)
    assert_package_wiring(project_dir, project_slug, package_name)
    smoke_test_runtime(project_dir, package_name)


def test_custom_slug_with_package_override(tmp_path: Path) -> None:
    project_slug = "acme-tool"
    package_name = "acme_cli"
    project_dir = render_template(tmp_path, project_slug=project_slug, package_name=package_name)

    assert_expected_files(project_dir, package_name)
    assert_no_unrendered_tokens(project_dir)
    assert_package_wiring(project_dir, project_slug, package_name)
    smoke_test_runtime(project_dir, package_name)


def test_invalid_author_email_fails_pre_gen(tmp_path: Path) -> None:
    with pytest.raises(FailedHookException):
        render_template(tmp_path, author_email="not-an-email")
