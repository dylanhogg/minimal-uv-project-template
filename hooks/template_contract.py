from __future__ import annotations

from pathlib import Path


def required_project_relative_paths(
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> tuple[str, ...]:
    return (
        ".github/workflows/ci.yml",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "scripts/vscode_launch.sh",
        "docs/template/vscode-debug-setup.md",
        f"apps/{app_slug}/pyproject.toml",
        f"apps/{app_slug}/src/{app_package}/app.py",
        f"apps/{app_slug}/tests/test_app.py",
        f"packages/{lib_slug}/pyproject.toml",
        f"packages/{lib_slug}/src/{lib_package}/env.py",
        f"packages/{lib_slug}/src/{lib_package}/log.py",
        f"packages/{lib_slug}/tests/test_env.py",
        f"packages/{lib_slug}/tests/test_log.py",
    )


def required_project_paths(
    root: Path,
    app_slug: str,
    app_package: str,
    lib_slug: str,
    lib_package: str,
) -> list[Path]:
    return [
        root / relative_path
        for relative_path in required_project_relative_paths(
            app_slug=app_slug,
            app_package=app_package,
            lib_slug=lib_slug,
            lib_package=lib_package,
        )
    ]
